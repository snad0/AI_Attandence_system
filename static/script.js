// script.js

document.addEventListener('DOMContentLoaded', function() {
    // Show the resident form when the button is clicked
    document.getElementById('add-resident-btn').addEventListener('click', function() {
        document.getElementById('resident-form').style.display = 'block';
    });

    // Hide the resident form when cancel is clicked
    document.getElementById('cancel-btn').addEventListener('click', function() {
        document.getElementById('resident-form').style.display = 'none';
        document.getElementById('resident-form-form').reset();
    });

    // Handle form submission
    document.getElementById('resident-form-form').addEventListener('submit', function(event) {
        event.preventDefault();
        var formData = new FormData();

        formData.append('name', document.getElementById('resident-name').value);
        formData.append('address', document.getElementById('resident-address').value);
        formData.append('block_no', document.getElementById('resident-block').value);
        formData.append('resident_type', document.getElementById('resident-type').value);

        var imageFile = document.getElementById('resident-image').files[0];
        if (imageFile) {
            formData.append('image', imageFile);
        }

        fetch('/add_resident', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            // Optionally refresh the attendance data
            fetchAttendance();
            document.getElementById('resident-form').style.display = 'none';
            document.getElementById('resident-form-form').reset();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while adding the resident.');
        });
    });

    // Function to fetch and update attendance data dynamically
    function fetchAttendance() {
        fetch('/fetch_attendance')
        .then(response => response.json())
        .then(data => {
            // Update the attendance table
            var tableBody = document.querySelector('#attendance-table tbody');
            tableBody.innerHTML = '';
            data.forEach(function(row) {
                var tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${row.date}</td>
                    <td>${row.name}</td>
                    <td>${row.entry_time || ''}</td>
                    <td>${row.exit_time || ''}</td>
                    <td>${row.re_entry}</td>
                    <td>${row.re_entry_time || ''}</td>
                    <td>${row.status}</td>
                `;
                tableBody.appendChild(tr);
            });
        })
        .catch(error => {
            console.error('Error fetching attendance data:', error);
        });
    }

    // Function to fetch and display logs
    function fetchLogs() {
        fetch('/fetch_logs')
        .then(response => response.json())
        .then(logs => {
            var logsDiv = document.getElementById('logs');
            logsDiv.innerHTML = ''; // Clear previous logs

            logs.forEach(function(log) {
                var p = document.createElement('p');
                p.textContent = log.trim(); // Add each log line to the logs section
                logsDiv.appendChild(p);
            });
        })
        .catch(error => {
            console.error('Error fetching logs:', error);
        });
    }




    // Fetch attendance data and logs periodically
    setInterval(fetchAttendance, 5000); // Update every 5 seconds
    setInterval(fetchLogs, 5000); // Update every 5 seconds

    // Initial fetch
    fetchAttendance();
    fetchLogs();
});
