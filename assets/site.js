document.querySelectorAll('[data-copy-email]').forEach(button => {
  button.addEventListener('click', async () => {
    const status = button.closest('.support-contact').querySelector('.email-status');
    try {
      await navigator.clipboard.writeText('getonlabs@gmail.com');
      status.textContent = 'Email address copied.';
    } catch {
      status.textContent = 'Please select and copy getonlabs@gmail.com above.';
    }
  });
});
