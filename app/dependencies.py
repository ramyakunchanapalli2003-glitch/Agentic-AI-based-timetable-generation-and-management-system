from fastapi import Request, HTTPException, status, Depends
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer

# Shared Templates
templates = Jinja2Templates(directory="templates")

# Shared Security
SECRET_KEY = "super-secret-key-for-mca-project"
serializer = URLSafeSerializer(SECRET_KEY)

async def get_current_user(request: Request):
    session = request.cookies.get("session")
    if not session:
        return None
    try:
        username = serializer.loads(session)
        return username
    except:
        return None

def login_required(user = Depends(get_current_user)):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return user
