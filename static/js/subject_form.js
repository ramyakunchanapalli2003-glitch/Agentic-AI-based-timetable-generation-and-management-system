let rowCounter = 0;

function addSubjectRow(name='', faculty='', type='Lecture', periods=3) {
    const container = document.getElementById('subjectsContainer');
    const rowId = ++rowCounter;
    
    const row = document.createElement('div');
    row.id = `row-${rowId}`;
    row.style = "display: grid; grid-template-columns: 2fr 2fr 1.5fr 1fr 50px; gap: 10px; margin-bottom: 10px; background: #fff; padding: 10px; border-radius: 8px; border: 1px solid #f0f0f0;";
    
    row.innerHTML = `
        <input type="text" class="sub-name" placeholder="E.g. Database" value="${name}" required>
        <input type="text" class="sub-faculty" placeholder="E.g. Dr. Ray" value="${faculty}" required>
        <select class="sub-type">
            <option value="Lecture" ${type === 'Lecture' ? 'selected' : ''}>Lecture</option>
            <option value="Lab" ${type === 'Lab' ? 'selected' : ''}>Lab</option>
        </select>
        <input type="number" class="sub-periods" min="1" max="6" value="${periods}" required>
        <button type="button" onclick="removeRow(${rowId})" style="background: none; border: none; color: #e74c3c; cursor: pointer; font-size: 1.2rem;">&times;</button>
    `;
    
    container.appendChild(row);
}

function removeRow(id) {
    const row = document.getElementById(`row-${id}`);
    if (row) row.remove();
}

// Initializing the form submission handler
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('timetableForm');
    if (!form) return;

    form.addEventListener('submit', function(e) {
        const subjects = [];
        const names = document.querySelectorAll('.sub-name');
        const faculties = document.querySelectorAll('.sub-faculty');
        const types = document.querySelectorAll('.sub-type');
        const periods = document.querySelectorAll('.sub-periods');
        
        for(let i=0; i<names.length; i++) {
            subjects.push({
                name: names[i].value,
                faculty: faculties[i].value,
                type: types[i].value,
                periods: parseInt(periods[i].value) || 3
            });
        }
        
        if(subjects.length < 3) {
            alert("Please add at least 3 subjects.");
            e.preventDefault();
            return false;
        }
        
        const hiddenInput = document.getElementById('subjects_json');
        if (hiddenInput) {
            hiddenInput.value = JSON.stringify(subjects);
        }
    });
});

