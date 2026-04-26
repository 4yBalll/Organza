document.addEventListener('DOMContentLoaded', () => {
    const phoneInput = document.querySelector('[data-phone-input]');
    const codeInput = document.querySelector('[data-code-input]');

    if (phoneInput) {
        phoneInput.addEventListener('input', () => {
            phoneInput.value = formatPhone(phoneInput.value);
        });

        phoneInput.addEventListener('focus', () => {
            if (!phoneInput.value) {
                phoneInput.value = '+7 ';
            }
        });
    }

    if (codeInput) {
        codeInput.focus();

        codeInput.addEventListener('input', () => {
            codeInput.value = codeInput.value.replace(/\D/g, '').slice(0, 4);
        });
    }
});

function formatPhone(value) {
    let digits = value.replace(/\D/g, '');

    if (digits.startsWith('8')) {
        digits = '7' + digits.slice(1);
    }

    if (digits.length === 10) {
        digits = '7' + digits;
    }

    digits = digits.slice(0, 11);

    if (!digits.length) {
        return '';
    }

    if (digits[0] !== '7') {
        digits = '7' + digits.slice(0, 10);
    }

    const local = digits.slice(1);

    let result = '+7';

    if (local.length > 0) {
        result += ' (' + local.slice(0, 3);
    }
    if (local.length >= 3) {
        result += ')';
    }
    if (local.length > 3) {
        result += ' ' + local.slice(3, 6);
    }
    if (local.length > 6) {
        result += '-' + local.slice(6, 8);
    }
    if (local.length > 8) {
        result += '-' + local.slice(8, 10);
    }

    return result;
}