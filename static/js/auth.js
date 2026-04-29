document.addEventListener('DOMContentLoaded', () => {
    const phoneInput = document.querySelector('[data-phone-input]');
    const codeInput = document.querySelector('[data-code-input]');

    if (phoneInput) {
        phoneInput.addEventListener('focus', () => {
            if (!phoneInput.value.trim()) {
                phoneInput.value = '+7 ';
            }
        });

        phoneInput.addEventListener('input', () => {
            phoneInput.value = formatPhone(phoneInput.value);
        });

        phoneInput.addEventListener('keydown', (event) => {
            const selectionStart = phoneInput.selectionStart ?? 0;
            const selectionEnd = phoneInput.selectionEnd ?? 0;

            const isPrefixArea = selectionStart <= 3 && selectionEnd <= 3;
            const isDeleteKey = event.key === 'Backspace' || event.key === 'Delete';

            if (isDeleteKey && isPrefixArea) {
                event.preventDefault();
            }
        });

        phoneInput.addEventListener('blur', () => {
            if (phoneInput.value.trim() === '+7') {
                phoneInput.value = '';
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

    // Если пользователь начал с 7 или 8, убираем этот символ,
    // потому что +7 уже зашит в маске.
    if (digits.startsWith('7') || digits.startsWith('8')) {
        digits = digits.slice(1);
    }

    // Только 10 цифр после +7
    digits = digits.slice(0, 10);

    let result = '+7';

    if (digits.length > 0) {
        result += ' (' + digits.slice(0, 3);
    }

    if (digits.length >= 4) {
        result += ') ' + digits.slice(3, 6);
    }

    if (digits.length >= 7) {
        result += '-' + digits.slice(6, 8);
    }

    if (digits.length >= 9) {
        result += '-' + digits.slice(8, 10);
    }

    return result;
}