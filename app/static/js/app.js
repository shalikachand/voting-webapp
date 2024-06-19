document.addEventListener('DOMContentLoaded', function() {
    // Function to open the add nominee modal
    window.openAddNomineeModal = function(yearLevel) {
        const modal = new bootstrap.Modal(document.getElementById('addNomineeModal'));
        document.getElementById('addNomineeForm').onsubmit = function(event) {
            event.preventDefault();
            addNominee(yearLevel);
            modal.hide();
        };
        modal.show();
    };

    // Function to add a nominee
    window.addNominee = function(yearLevel) {
        const name = document.getElementById('nomineeName').value;
        const imageInput = document.getElementById('nomineeImage');
        const image = URL.createObjectURL(imageInput.files[0]);
        const nomineeCard = document.createElement('div');
        nomineeCard.className = 'card mb-3';
        nomineeCard.innerHTML = `
            <img src="${image}" class="card-img-top" alt="Nominee Image">
            <div class="card-body">
                <h5 class="card-title">${name}</h5>
                <button class="btn btn-danger" onclick="deleteNominee(this)">Delete</button>
            </div>
        `;
        document.getElementById(`${yearLevel}-nominees`).appendChild(nomineeCard);
    };

    // Function to delete a nominee
    window.deleteNominee = function(button) {
        button.closest('.card').remove();
    };

    // Function to handle the finish button
    window.finishEditing = function() {
        alert('Editing finished');
        // Submit the changes to the server or handle accordingly
        // Example: document.getElementById('nomineeForm').submit();
    };
});
