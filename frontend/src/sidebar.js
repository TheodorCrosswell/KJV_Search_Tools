document.addEventListener('DOMContentLoaded', () => {
        document.getElementById('sidebar-toggle').addEventListener('click', function () {
            document.getElementById('sidebar').classList.toggle('open');
        });
});