"""
Gemini Planning Agent
---------------------
Coordinates the timetable generation workflow using Google Gemini as the
planning/decision-making layer.  The agent treats the existing generation,
validation, and save logic as *tools* that Gemini can invoke.

Gemini parses general natural-language scheduling instructions into generic
constraint objects and passes them to the Python generation and validation
algorithms.

Gemini never creates timetable slots itself – it only decides which tool
to call next based on the results returned by each tool.

Uses the modern `google-genai` SDK.
"""

import os
import json
import datetime
import traceback

from app.agents.generation import GenerationAgent, match_subject
from app.agents.validation import ValidationAgent


# ---------------------------------------------------------------------------
# Try to import the Gemini SDK. If missing, fall back gracefully.
# ---------------------------------------------------------------------------
try:
    from google import genai
    from google.genai import types

    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Tool function declarations for the Gemini model
# ---------------------------------------------------------------------------
_GENERATE_DECL = types.FunctionDeclaration(
    name="generate_timetable",
    description=(
        "Generate a new timetable using the constraint-aware algorithm. "
        "Returns a JSON object with keys 'success' (bool) and 'logs' (list of strings). "
        "If success is true, the timetable data is stored internally."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={},
    ),
)

_VALIDATE_DECL = types.FunctionDeclaration(
    name="validate_timetable",
    description=(
        "Validate the most recently generated timetable against all "
        "constraints (period counts, lunch break, lab continuity, "
        "faculty collisions, custom rules). Returns a JSON object with 'valid' (bool) "
        "and 'logs' (list of strings describing any errors)."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={},
    ),
)

_REGENERATE_DECL = types.FunctionDeclaration(
    name="regenerate_timetable",
    description=(
        "Discard the current timetable and generate a brand-new one. "
        "Use this when validation has failed. Returns the same schema "
        "as generate_timetable."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={},
    ),
)

_SAVE_DECL = types.FunctionDeclaration(
    name="save_timetable",
    description=(
        "Persist the validated timetable to the database and record all "
        "agent logs. Call this only after validation succeeds. "
        "Returns a JSON object with 'saved' (bool) and 'timetable_id' (int)."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={},
    ),
)

_TOOL = types.Tool(function_declarations=[
    _GENERATE_DECL, _VALIDATE_DECL, _REGENERATE_DECL, _SAVE_DECL
])


class PlanningAgent:
    """Gemini-powered orchestrator for the timetable pipeline."""

    MAX_ATTEMPTS = 3  # hard cap on generate→validate cycles

    def __init__(
        self,
        db,
        subjects,
        department,
        course,
        semester,
        busy_faculty,
        ai_instruction="",
        *,
        existing_tt=None,
    ):
        """
        Parameters
        ----------
        db : sqlalchemy.orm.Session
        subjects : list[dict]
        department, course, semester : str / int
        busy_faculty : dict   – day → slot_idx → set(normalized faculty)
        ai_instruction : str  – optional natural-language hint from the admin
        existing_tt : Timetable | None – if regenerating an existing record
        """
        self.db = db
        self.subjects = subjects
        self.department = department
        self.course = course
        self.semester = semester
        self.busy_faculty = busy_faculty
        self.ai_instruction = ai_instruction or ""
        self.existing_tt = existing_tt

        # Internal state
        self._timetable_data = None
        self._all_logs: list[str] = []
        self._attempt = 0
        self.custom_constraints = []
        self.conflict_diagnostic = None

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------
    def _log(self, message: str):
        timestamp = datetime.datetime.utcnow().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self._all_logs.append(entry)
        print(f"[PlanningAgent] {entry}")

    # ------------------------------------------------------------------
    # Natural Language Instruction Parser via Gemini
    # ------------------------------------------------------------------
    def _parse_instructions(self, client) -> list:
        """
        Uses Gemini LLM to parse generic natural-language instructions into structured constraints.
        Remaps parsed target subjects directly to configured subject names.
        """
        if not self.ai_instruction or not self.ai_instruction.strip():
            return []

        subject_names = [s['name'] for s in self.subjects]
        
        prompt = (
            f"You are an expert academic scheduling constraint parser. "
            f"Extract any specific scheduling preferences/constraints from the administrator's instruction.\n\n"
            f"Available Subjects in this request: {json.dumps(subject_names)}\n"
            f"Available Days: [\"Monday\", \"Tuesday\", \"Wednesday\", \"Thursday\", \"Friday\", \"Saturday\"]\n\n"
            f"Admin Instruction: \"{self.ai_instruction}\"\n\n"
            f"Respond ONLY with a valid JSON array of constraint objects. Do NOT include markdown code blocks or explanations.\n"
            f"Each constraint object must have:\n"
            f"- \"subject\": Choose the closest matching subject name from the available subjects list.\n"
            f"- \"type\": One of [\"pin_day\", \"avoid_day\", \"before_lunch\", \"after_lunch\", \"time_preference\"]\n"
            f"- \"day\": Target day string (e.g. \"Monday\", \"Wednesday\") if specified, else null.\n"
            f"- \"time_range\": \"morning\", \"afternoon\", \"before_lunch\", or \"after_lunch\" if specified, else null.\n"
            f"- \"raw_instruction\": The text snippet representing this request.\n\n"
            f"Example Output:\n"
            f"[{{\"subject\": \"Database Lab\", \"type\": \"pin_day\", \"day\": \"Monday\", \"time_range\": \"afternoon\", \"raw_instruction\": \"Schedule Database Lab on Monday afternoon.\"}}]\n"
        )
        
        try:
            resp = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = resp.text.strip()
            if "```" in text:
                parts = text.split("```")
                for p in parts:
                    clean_p = p.strip()
                    if clean_p.startswith("json"):
                        clean_p = clean_p[4:].strip()
                    if clean_p.startswith("["):
                        text = clean_p
                        break
            parsed = json.loads(text)
            if isinstance(parsed, list):
                if not parsed:
                    self._log("Gemini returned empty constraints – falling back to local parser.")
                    return self._parse_instructions_local()

                # Remap target subject names to exact configured subjects
                for c in parsed:
                    target = c.get("subject", "")
                    for s in self.subjects:
                        if match_subject(target, s['name']):
                            c["subject"] = s['name']
                            break

                self._log(f"Planning – Parsed instruction into {len(parsed)} constraint(s): {json.dumps(parsed)}")
                return parsed
        except Exception as exc:
            self._log(f"Warning: Could not parse custom AI instruction via Gemini ({exc}). Falling back to local parser.")
            return self._parse_instructions_local()
        
        return self._parse_instructions_local()

    # ------------------------------------------------------------------
    # Rule-based fallback instruction parser (no Gemini required)
    # ------------------------------------------------------------------
    def _parse_instructions_local(self) -> list:
        """
        Keyword & pattern-based parser used when Gemini is unavailable or fails.
        Extracts pin_day, avoid_day, before_lunch, after_lunch constraints
        from the admin's natural-language instruction.
        """
        if not self.ai_instruction or not self.ai_instruction.strip():
            return []

        import re
        raw_text = self.ai_instruction.strip()
        # Clean punctuation for token matching, preserving word boundaries
        text = re.sub(r'[^\w\s]', ' ', raw_text.lower())
        DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        constraints = []

        STOP_WORDS = {
            "schedule", "keep", "place", "put", "assign", "avoid", "not", "on",
            "in", "the", "a", "an", "for", "before", "after", "lunch", "morning",
            "afternoon", "forenoon", "class", "subject", "prefer", "labs", "lab",
            "do", "don't", "exclude", "no", "is", "should", "be", "at", "to",
        }
        ALL_DAYS_SET = set(DAYS)

        def find_subject(t_str):
            words = t_str.split()
            subject_tokens = [w for w in words if w not in STOP_WORDS and w not in ALL_DAYS_SET]
            subject_phrase = " ".join(subject_tokens)

            for s in self.subjects:
                if match_subject(subject_phrase, s['name']):
                    return s['name']
            for length in range(len(subject_tokens), 0, -1):
                for start in range(len(subject_tokens) - length + 1):
                    chunk = " ".join(subject_tokens[start:start+length])
                    for s in self.subjects:
                        if match_subject(chunk, s['name']):
                            return s['name']
            return None

        subject = find_subject(text)

        matched_day = None
        for day in DAYS:
            if day in text:
                matched_day = day.capitalize()
                break

        matched_time = None
        if any(kw in text for kw in ["before lunch", "morning", "forenoon", "first half"]):
            matched_time = "before_lunch"
        elif any(kw in text for kw in ["after lunch", "afternoon", "post lunch", "second half"]):
            matched_time = "after_lunch"

        if matched_day:
            ctype = "avoid_day" if any(kw in text for kw in ["avoid", "not on", "exclude", "no class on", "don't schedule", "do not schedule"]) else "pin_day"
            if subject:
                constraints.append({
                    "subject": subject,
                    "type": ctype,
                    "day": matched_day,
                    "time_range": matched_time,
                    "raw_instruction": raw_text,
                })
        elif matched_time and subject:
            constraints.append({
                "subject": subject,
                "type": matched_time,
                "day": None,
                "time_range": matched_time,
                "raw_instruction": raw_text,
            })

        self._log(f"Local parser – extracted {len(constraints)} constraint(s): {json.dumps(constraints)}")
        return constraints

    # ------------------------------------------------------------------
    # Tool implementations (thin wrappers around existing agents)
    # ------------------------------------------------------------------
    def _tool_generate(self) -> dict:
        self._attempt += 1
        self._log(f"Generation – attempt {self._attempt}/{self.MAX_ATTEMPTS}")
        gen = GenerationAgent(
            self.subjects, 
            busy_faculty=self.busy_faculty, 
            custom_constraints=self.custom_constraints
        )
        data, logs = gen.generate()
        self._all_logs.extend(logs)
        if data is not None:
            self._timetable_data = data
            return {"success": True, "logs": logs}
        else:
            if gen.last_conflict_report:
                self.conflict_diagnostic = gen.last_conflict_report
            return {"success": False, "logs": logs}

    def _tool_validate(self) -> dict:
        self._log("Validation – checking constraints")
        if self._timetable_data is None:
            msg = "No timetable data to validate."
            self._log(msg)
            return {"valid": False, "logs": [msg]}
        val = ValidationAgent(
            self.subjects, 
            self._timetable_data, 
            busy_faculty=self.busy_faculty,
            custom_constraints=self.custom_constraints
        )
        valid, logs = val.validate()
        self._all_logs.extend(logs)
        return {"valid": valid, "logs": logs}

    def _tool_regenerate(self) -> dict:
        self._log("Regeneration – discarding previous timetable")
        self._timetable_data = None
        return self._tool_generate()

    def _tool_save(self) -> dict:
        from app.models.database import Timetable, AgentLog

        self._log("Timetable Saved – persisting to database")

        if self.existing_tt is not None:
            # Regeneration path – update existing record
            tt = self.existing_tt
            tt.department = self.department
            tt.course = self.course
            tt.semester = self.semester
            tt.subject_config = self.subjects
            tt.generated_data = self._timetable_data

            self.db.query(AgentLog).filter(
                AgentLog.timetable_id == tt.id
            ).delete()
        else:
            tt = Timetable(
                department=self.department,
                course=self.course,
                semester=self.semester,
                subject_config=self.subjects,
                generated_data=self._timetable_data,
            )
            self.db.add(tt)
            self.db.flush()

        # Write all accumulated logs
        for msg in self._all_logs:
            status = "INFO"
            lower = msg.lower()
            if "success" in lower or "passed" in lower or "saved" in lower:
                status = "SUCCESS"
            elif "error" in lower or "failed" in lower:
                status = "FAILED"
            self.db.add(
                AgentLog(
                    timetable_id=tt.id,
                    agent_name="GeminiPlanningAgent",
                    message=msg,
                    status=status,
                )
            )
        self.db.commit()
        return {"saved": True, "timetable_id": tt.id}

    # ------------------------------------------------------------------
    # Dispatch a tool call by name
    # ------------------------------------------------------------------
    def _dispatch_tool(self, name: str) -> dict:
        handlers = {
            "generate_timetable": self._tool_generate,
            "validate_timetable": self._tool_validate,
            "regenerate_timetable": self._tool_regenerate,
            "save_timetable": self._tool_save,
        }
        fn = handlers.get(name)
        if fn is None:
            return {"error": f"Unknown tool: {name}"}
        return fn()

    # ------------------------------------------------------------------
    # Build the system prompt for Gemini
    # ------------------------------------------------------------------
    def _build_system_prompt(self) -> str:
        return (
            "You are a Timetable Planning Agent. Your role is to coordinate "
            "the creation of a valid academic timetable by calling the "
            "available tools in the correct order.\n\n"
            "WORKFLOW:\n"
            "1. Call generate_timetable to create the initial schedule.\n"
            "2. Call validate_timetable to check constraints.\n"
            "3. If validation fails, call regenerate_timetable (max 3 total attempts).\n"
            "4. If validation succeeds, call save_timetable.\n"
            "5. After saving, respond with a brief summary.\n\n"
            "RULES:\n"
            "- You must NOT generate timetable slots yourself.\n"
            "- You must only call the provided tools.\n"
            "- Do not exceed 3 generation attempts total.\n"
            "- If all 3 attempts fail validation, respond explaining the failure.\n"
            "- Always call validate_timetable after each generation.\n"
            "- Only call save_timetable after a successful validation.\n"
        )

    # ------------------------------------------------------------------
    # Build the user message
    # ------------------------------------------------------------------
    def _build_user_message(self) -> str:
        config_summary = (
            f"Department: {self.department}, Course: {self.course}, "
            f"Semester: {self.semester}\n"
            f"Subjects: {json.dumps(self.subjects, indent=2)}\n"
        )
        if self.ai_instruction:
            config_summary += f"\nAdmin instruction: {self.ai_instruction}\n"

        action = "regenerate" if self.existing_tt else "generate"
        return (
            f"Please {action} a timetable with the following configuration:\n\n"
            f"{config_summary}\n"
            "Start by calling generate_timetable."
        )

    # ------------------------------------------------------------------
    # Run the Gemini agentic loop
    # ------------------------------------------------------------------
    def _ensure_conflict_diagnostic(self):
        if self.conflict_diagnostic:
            return
        if not self.custom_constraints:
            return
        c = self.custom_constraints[0]
        target_sub = c.get("subject")
        target_subject_dict = None
        if target_sub:
            for s in self.subjects:
                if match_subject(target_sub, s['name']):
                    target_subject_dict = s
                    break
        if not target_subject_dict and self.subjects:
            target_subject_dict = self.subjects[0]
        
        if target_subject_dict:
            gen = GenerationAgent(self.subjects, busy_faculty=self.busy_faculty, custom_constraints=self.custom_constraints)
            self.conflict_diagnostic = gen.analyze_conflict(target_subject_dict)

    def run(self) -> dict:
        """
        Returns
        -------
        dict with keys:
            success : bool
            timetable_id : int | None
            logs : list[str]
            error : str | None
        """
        self._log("Agent Started")

        # ---- Gate: is Gemini usable? ----
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not _GEMINI_AVAILABLE or not api_key:
            reason = (
                "google-genai SDK not installed"
                if not _GEMINI_AVAILABLE
                else "GEMINI_API_KEY not set"
            )
            self._log(f"Gemini unavailable ({reason}) – using direct fallback pipeline")
            if self.ai_instruction:
                self._log("Parsing instruction with local rule-based parser (Gemini unavailable)")
                self.custom_constraints = self._parse_instructions_local()
            return self._fallback_pipeline()

        # ---- Configure Gemini client ----
        try:
            client = genai.Client(api_key=api_key)
        except Exception as exc:
            self._log(f"Gemini init error: {exc} – falling back")
            return self._fallback_pipeline()

        # ---- Parse Natural Language Instructions into Structured Constraints ----
        if self.ai_instruction:
            self.custom_constraints = self._parse_instructions(client)

        # ---- Start chat and agentic tool-call loop ----
        self._log("Planning – sending request to Gemini")
        try:
            chat = client.chats.create(
                model="gemini-2.0-flash",
                config=types.GenerateContentConfig(
                    system_instruction=self._build_system_prompt(),
                    tools=[_TOOL],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
            response = chat.send_message(self._build_user_message())

            loop_guard = 0
            max_loops = 12  # safety net

            while loop_guard < max_loops:
                loop_guard += 1

                # Check for function calls in the response
                function_calls = response.function_calls
                if not function_calls:
                    final_text = response.text if response.text else ""
                    self._log(f"Completed – Gemini summary: {final_text[:200]}")
                    break

                # Execute each function call and collect results
                tool_responses = []
                for fc in function_calls:
                    fn_name = fc.name
                    self._log(f"Planning – Gemini called tool: {fn_name}")

                    if fn_name in ("generate_timetable", "regenerate_timetable"):
                        if self._attempt >= self.MAX_ATTEMPTS:
                            result = {
                                "success": False,
                                "logs": [
                                    f"Maximum {self.MAX_ATTEMPTS} attempts reached. "
                                    "Cannot generate again."
                                ],
                            }
                            self._log("Generation blocked – max attempts reached")
                        else:
                            result = self._dispatch_tool(fn_name)
                    else:
                        result = self._dispatch_tool(fn_name)

                    tool_responses.append(
                        types.FunctionResponse(
                            name=fn_name,
                            response=result,
                        )
                    )

                response = chat.send_message(tool_responses)

        except Exception as exc:
            self._log(f"Gemini API rate limited or unavailable ({type(exc).__name__}) – seamlessly using local fallback engine.")
            return self._fallback_pipeline()

        # ---- Determine outcome ----
        saved_id = self._find_saved_id()
        if saved_id:
            return {
                "success": True,
                "timetable_id": saved_id,
                "logs": self._all_logs,
                "error": None,
            }

        # Gemini finished but never saved – treat as failure with diagnostic message
        self._log("Agent finished without saving – generation unsuccessful")
        self._ensure_conflict_diagnostic()
        
        error_msg = "Failed to generate a valid timetable after all attempts."
        if self.conflict_diagnostic:
            d = self.conflict_diagnostic
            reasons_text = " ".join(d.get("conflict_reasons", []))
            alts = d.get("alternative_slots", [])
            alts_text = f" Alternative valid available slot(s): {', '.join(alts)}." if alts else " No alternative slots available on other days."
            
            error_msg = (
                f"Scheduling Instruction Conflict: Cannot fulfill instruction '{d.get('instruction')}' for '{d.get('subject')}' (Faculty: {d.get('faculty')}). "
                f"Requested Target: {d.get('requested_target')}. Reason: {reasons_text}{alts_text}"
            )

        return {
            "success": False,
            "timetable_id": None,
            "logs": self._all_logs,
            "error": error_msg,
        }

    # ------------------------------------------------------------------
    # Fallback: run the direct pipeline
    # ------------------------------------------------------------------
    def _fallback_pipeline(self) -> dict:
        self._log("Fallback – running direct generation pipeline")

        gen_result = self._tool_generate()
        if not gen_result["success"]:
            self._log("Fallback – generation failed")
            self._ensure_conflict_diagnostic()
            error_msg = "Generation failed."
            if self.conflict_diagnostic:
                d = self.conflict_diagnostic
                reasons_text = " ".join(d.get("conflict_reasons", []))
                alts = d.get("alternative_slots", [])
                alts_text = f" Alternative valid available slot(s): {', '.join(alts)}." if alts else " No alternative slots available on other days."
                error_msg = (
                    f"Scheduling Instruction Conflict: Cannot fulfill instruction '{d.get('instruction')}' for '{d.get('subject')}' (Faculty: {d.get('faculty')}). "
                    f"Requested Target: {d.get('requested_target')}. Reason: {reasons_text}{alts_text}"
                )
            return {
                "success": False,
                "timetable_id": None,
                "logs": self._all_logs,
                "error": error_msg,
            }

        val_result = self._tool_validate()
        if not val_result["valid"]:
            while self._attempt < self.MAX_ATTEMPTS:
                self._log("Fallback – validation failed, regenerating")
                regen = self._tool_regenerate()
                if not regen["success"]:
                    continue
                val_result = self._tool_validate()
                if val_result["valid"]:
                    break

        if not val_result["valid"]:
            self._log("Fallback – all attempts exhausted")
            self._ensure_conflict_diagnostic()
            error_msg = "Failed to generate valid timetable."
            if self.conflict_diagnostic:
                d = self.conflict_diagnostic
                reasons_text = " ".join(d.get("conflict_reasons", []))
                alts = d.get("alternative_slots", [])
                alts_text = f" Alternative valid available slot(s): {', '.join(alts)}." if alts else " No alternative slots available on other days."
                error_msg = (
                    f"Scheduling Instruction Conflict: Cannot fulfill instruction '{d.get('instruction')}' for '{d.get('subject')}' (Faculty: {d.get('faculty')}). "
                    f"Requested Target: {d.get('requested_target')}. Reason: {reasons_text}{alts_text}"
                )
            return {
                "success": False,
                "timetable_id": None,
                "logs": self._all_logs,
                "error": error_msg,
            }

        save_result = self._tool_save()
        self._log("Completed")
        return {
            "success": True,
            "timetable_id": save_result.get("timetable_id"),
            "logs": self._all_logs,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Helper: extract saved timetable id
    # ------------------------------------------------------------------
    def _find_saved_id(self) -> int | None:
        for log in reversed(self._all_logs):
            if "Timetable Saved" in log:
                from app.models.database import Timetable

                if self.existing_tt:
                    return self.existing_tt.id
                tt = (
                    self.db.query(Timetable)
                    .filter(
                        Timetable.department == self.department,
                        Timetable.course == self.course,
                        Timetable.semester == self.semester,
                    )
                    .order_by(Timetable.id.desc())
                    .first()
                )
                return tt.id if tt else None
        return None
