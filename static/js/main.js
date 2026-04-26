const tables = document.querySelectorAll('.table');

const tooltip = document.getElementById('tableTooltip');
const title = document.getElementById('tooltipTitle');
const tooltipImg = document.getElementById('tooltipImg');
const tooltipContent = document.getElementById('tooltipDescription');
const openPanoramaBtn = document.getElementById('openPanoramaBtn');

const panoramaModal = document.getElementById('panoramaModal');
const panoramaBackdrop = document.getElementById('panoramaBackdrop');
const panoramaImg = document.getElementById('panoramaImg');
const panoramaTitle = document.getElementById('panoramaTitle');
const closePanoramaBtn = document.getElementById('closePanoramaBtn');
const panoramaViewer = document.getElementById('panoramaViewer');

const bookingSection = document.getElementById('booking');
const bookingDateInput = document.getElementById('bookingDate');
const bookingTimeSelect = document.getElementById('bookingTime');
const bookingDurationSelect = document.getElementById('bookingDuration');
const checkAvailabilityBtn = document.getElementById('checkAvailabilityBtn');
const createBookingBtn = document.getElementById('createBookingBtn');
const bookingMessage = document.getElementById('bookingMessage');
const bookingComment = document.getElementById('bookingComment');
const selectedTablesBox = document.getElementById('selectedTablesBox');

const freeTablesCount = document.getElementById('freeTablesCount');
const occupiedTablesCount = document.getElementById('occupiedTablesCount');
const selectedTablesCount = document.getElementById('selectedTablesCount');

const summaryDate = document.getElementById('summaryDate');
const summaryTime = document.getElementById('summaryTime');
const summaryTables = document.getElementById('summaryTables');
const summarySeats = document.getElementById('summarySeats');
const bookingSummaryStatus = document.getElementById('bookingSummaryStatus');

const isAuthenticated = bookingSection?.dataset.authenticated === 'true';
const loginUrl = bookingSection?.dataset.loginUrl || '/auth/login';

const DEFAULT_DURATION_MINUTES = 120;
const MAX_TABLES_PER_RESERVATION = 2;
const OPEN_HOUR = 10;
const CLOSE_HOUR = 22;
const LAST_START_HOUR = 21;
const SLOT_STEP_MINUTES = 30;

let currentTableData = null;
let hideTooltipTimer = null;

let isDragging = false;
let startX = 0;
let startY = 0;
let startScrollLeft = 0;
let startScrollTop = 0;

let touchStartX = 0;
let touchStartY = 0;
let touchStartScrollLeft = 0;
let touchStartScrollTop = 0;

let availabilityLoaded = false;
let selectedTableIds = [];
let availableTableIds = new Set();
let occupiedTableIds = new Set();
let tableMetaById = new Map();

let availabilityRequestId = 0;
let autoLoadTimer = null;

function showTooltip() {
    clearTimeout(hideTooltipTimer);
    tooltip.style.display = 'block';
}

function hideTooltipWithDelay() {
    clearTimeout(hideTooltipTimer);
    hideTooltipTimer = setTimeout(() => {
        tooltip.style.display = 'none';
    }, 220);
}

function hideTooltipNow() {
    clearTimeout(hideTooltipTimer);
    tooltip.style.display = 'none';
}

function setTooltipPosition(pageX, pageY) {
    tooltip.style.left = `${pageX + 8}px`;
    tooltip.style.top = `${pageY + 8}px`;
}

function formatDateToIso(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function formatDateForHuman(isoDate) {
    if (!isoDate) return '—';

    const [year, month, day] = isoDate.split('-');
    if (!year || !month || !day) return isoDate;

    return `${day}.${month}.${year}`;
}

function addOneMonth(date) {
    const sourceYear = date.getFullYear();
    const sourceMonth = date.getMonth();
    const sourceDay = date.getDate();

    const targetMonthDate = new Date(sourceYear, sourceMonth + 1, 1);
    const targetYear = targetMonthDate.getFullYear();
    const targetMonth = targetMonthDate.getMonth();

    const lastDay = new Date(targetYear, targetMonth + 1, 0).getDate();
    const safeDay = Math.min(sourceDay, lastDay);

    return new Date(targetYear, targetMonth, safeDay);
}

function addMinutesToTimeString(timeString, minutesToAdd) {
    const [hours, minutes] = timeString.split(':').map(Number);
    const totalMinutes = hours * 60 + minutes + minutesToAdd;
    const endHours = String(Math.floor(totalMinutes / 60)).padStart(2, '0');
    const endMinutes = String(totalMinutes % 60).padStart(2, '0');
    return `${endHours}:${endMinutes}`;
}

function formatDurationLabel(totalMinutes) {
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;

    if (hours > 0 && minutes > 0) {
        return `${hours} ч ${minutes} мин`;
    }

    if (hours > 0) {
        return `${hours} ч`;
    }

    return `${minutes} мин`;
}

function populateTimeOptions() {
    if (!bookingTimeSelect) return;

    bookingTimeSelect.innerHTML = '';

    for (let minutes = OPEN_HOUR * 60; minutes <= LAST_START_HOUR * 60; minutes += SLOT_STEP_MINUTES) {
        const hours = String(Math.floor(minutes / 60)).padStart(2, '0');
        const mins = String(minutes % 60).padStart(2, '0');
        const value = `${hours}:${mins}`;

        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;

        bookingTimeSelect.appendChild(option);
    }

    if ([...bookingTimeSelect.options].some((option) => option.value === '18:00')) {
        bookingTimeSelect.value = '18:00';
    }
}

function populateDurationOptions() {
    if (!bookingDurationSelect || !bookingTimeSelect) return;

    const selectedTime = bookingTimeSelect.value;
    const previousValue = Number(bookingDurationSelect.value || DEFAULT_DURATION_MINUTES);

    if (!selectedTime) {
        bookingDurationSelect.innerHTML = '';
        return;
    }

    const [hours, minutes] = selectedTime.split(':').map(Number);
    const startTotalMinutes = hours * 60 + minutes;
    const closeTotalMinutes = CLOSE_HOUR * 60;
    const maxAvailableDuration = closeTotalMinutes - startTotalMinutes;

    bookingDurationSelect.innerHTML = '';

    for (let duration = 30; duration <= maxAvailableDuration; duration += 30) {
        const option = document.createElement('option');
        option.value = String(duration);
        option.textContent = formatDurationLabel(duration);
        bookingDurationSelect.appendChild(option);
    }

    const availableValues = [...bookingDurationSelect.options].map((option) => Number(option.value));

    if (availableValues.includes(previousValue)) {
        bookingDurationSelect.value = String(previousValue);
    } else if (availableValues.includes(DEFAULT_DURATION_MINUTES)) {
        bookingDurationSelect.value = String(DEFAULT_DURATION_MINUTES);
    } else if (availableValues.length > 0) {
        bookingDurationSelect.value = String(availableValues[availableValues.length - 1]);
    }
}

function initializeBookingForm() {
    if (!bookingDateInput || !bookingTimeSelect || !bookingDurationSelect) return;

    const today = new Date();
    const maxDate = addOneMonth(today);

    bookingDateInput.min = formatDateToIso(today);
    bookingDateInput.max = formatDateToIso(maxDate);
    bookingDateInput.value = formatDateToIso(today);

    populateTimeOptions();
    populateDurationOptions();
    updateSummary();
    updateCreateBookingButtonState();
    renderSelectedTables();
}

function getSelectedBookingDate() {
    return bookingDateInput?.value || '';
}

function getSelectedBookingTime() {
    return bookingTimeSelect?.value || '';
}

function getSelectedBookingDuration() {
    return Number(bookingDurationSelect?.value || DEFAULT_DURATION_MINUTES);
}

function showBookingMessage(message, type = 'info') {
    if (!bookingMessage) return;

    bookingMessage.textContent = message;
    bookingMessage.className = `booking-message booking-message--${type}`;
}

function updateCreateBookingButtonState() {
    if (!createBookingBtn) return;

    createBookingBtn.disabled = !isAuthenticated || !availabilityLoaded || selectedTableIds.length === 0;
}

function updateBookingStats() {
    if (freeTablesCount) {
        freeTablesCount.textContent = availabilityLoaded ? String(availableTableIds.size) : '—';
    }

    if (occupiedTablesCount) {
        occupiedTablesCount.textContent = availabilityLoaded ? String(occupiedTableIds.size) : '—';
    }

    if (selectedTablesCount) {
        selectedTablesCount.textContent = String(selectedTableIds.length);
    }
}

function updateSummary() {
    const selectedDuration = getSelectedBookingDuration();
    const selectedTime = getSelectedBookingTime();

    if (summaryDate) {
        summaryDate.textContent = formatDateForHuman(getSelectedBookingDate());
    }

    if (summaryTime) {
        summaryTime.textContent = selectedTime
            ? `${selectedTime}–${addMinutesToTimeString(selectedTime, selectedDuration)}`
            : '—';
    }

    if (summaryTables) {
        if (selectedTableIds.length === 0) {
            summaryTables.textContent = 'Не выбраны';
        } else {
            summaryTables.textContent = selectedTableIds
                .map((tableId) => {
                    const tableMeta = tableMetaById.get(tableId);
                    return `№${tableMeta?.number ?? tableId}`;
                })
                .join(', ');
        }
    }

    if (summarySeats) {
        const totalSeats = selectedTableIds.reduce((sum, tableId) => {
            const tableMeta = tableMetaById.get(tableId);
            return sum + (tableMeta?.seats || 0);
        }, 0);

        summarySeats.textContent = String(totalSeats);
    }

    if (bookingSummaryStatus) {
        if (!availabilityLoaded) {
            bookingSummaryStatus.textContent = 'Загружаем доступность';
            bookingSummaryStatus.className = 'booking-summary__status booking-summary__status--loading';
        } else if (selectedTableIds.length === 0) {
            bookingSummaryStatus.textContent = 'Выберите столы';
            bookingSummaryStatus.className = 'booking-summary__status booking-summary__status--idle';
        } else {
            bookingSummaryStatus.textContent = 'Готово к бронированию';
            bookingSummaryStatus.className = 'booking-summary__status booking-summary__status--ready';
        }
    }

    updateBookingStats();
}

function renderSelectedTables() {
    if (!selectedTablesBox) return;

    if (selectedTableIds.length === 0) {
        selectedTablesBox.innerHTML = `
            <div class="selected-tables__empty">
                Пока не выбрано ни одного стола
            </div>
        `;
        updateSummary();
        updateCreateBookingButtonState();
        return;
    }

    selectedTablesBox.innerHTML = '';

    selectedTableIds.forEach((tableId) => {
        const tableMeta = tableMetaById.get(tableId);
        const item = document.createElement('div');
        item.className = 'selected-table-chip';

        item.innerHTML = `
            <div class="selected-table-chip__meta">
                <strong>Стол №${tableMeta?.number ?? tableId}</strong>
                <span>${tableMeta?.seats ?? '—'} мест</span>
            </div>
            <button type="button" class="selected-table-chip__remove" data-remove-table-id="${tableId}">
                ×
            </button>
        `;

        selectedTablesBox.appendChild(item);
    });

    updateSummary();
    updateCreateBookingButtonState();
}

function syncTableSelectionClasses() {
    tables.forEach((table) => {
        const tableId = Number(table.dataset.tableId);
        table.classList.toggle('is-selected', selectedTableIds.includes(tableId));
    });
}

function resetAvailabilityState({ preserveMessage = false, message = null } = {}) {
    availabilityLoaded = false;
    availableTableIds = new Set();
    occupiedTableIds = new Set();
    selectedTableIds = [];
    tableMetaById = new Map();

    tables.forEach((table) => {
        table.classList.remove('is-available', 'is-unavailable', 'is-selected');
    });

    renderSelectedTables();
    syncTableSelectionClasses();
    updateCreateBookingButtonState();
    updateSummary();

    if (!preserveMessage) {
        showBookingMessage(message || 'Обновляем доступность столов для выбранного времени.', 'info');
    }
}

function applyAvailabilityData(data) {
    availabilityLoaded = true;
    availableTableIds = new Set((data.available_table_ids || []).map(Number));
    occupiedTableIds = new Set((data.occupied_table_ids || []).map(Number));
    tableMetaById = new Map((data.tables || []).map((table) => [Number(table.id), table]));

    selectedTableIds = selectedTableIds.filter((tableId) => availableTableIds.has(tableId));

    tables.forEach((table) => {
        const tableId = Number(table.dataset.tableId);

        table.classList.remove('is-available', 'is-unavailable', 'is-selected');

        if (availableTableIds.has(tableId)) {
            table.classList.add('is-available');
        } else {
            table.classList.add('is-unavailable');
        }
    });

    syncTableSelectionClasses();
    renderSelectedTables();
    updateCreateBookingButtonState();
    updateSummary();
}

async function loadAvailability({ silent = false } = {}) {
    const selectedDate = getSelectedBookingDate();
    const selectedTime = getSelectedBookingTime();
    const selectedDuration = getSelectedBookingDuration();

    if (!selectedDate || !selectedTime || !selectedDuration) {
        showBookingMessage('Выберите дату, время и длительность.', 'error');
        return;
    }

    const currentRequestId = ++availabilityRequestId;

    if (!silent) {
        showBookingMessage('Загружаем свободные столы...', 'info');
    }

    try {
        const params = new URLSearchParams({
            date: selectedDate,
            time_start: selectedTime,
            duration_minutes: String(selectedDuration)
        });

        const response = await fetch(`/booking/available-tables?${params.toString()}`);
        const data = await response.json();

        if (currentRequestId !== availabilityRequestId) {
            return;
        }

        if (!response.ok) {
            throw new Error(data.error || 'Не удалось загрузить доступные столы.');
        }

        applyAvailabilityData(data);

        const freeCount = data.available_table_ids.length;

        if (freeCount === 0) {
            showBookingMessage('На выбранный интервал свободных столов нет. Попробуйте изменить параметры.', 'error');
        } else if (!silent) {
            showBookingMessage(`Свободных столов на выбранный интервал: ${freeCount}. Выберите не более двух.`, 'success');
        }
    } catch (error) {
        if (currentRequestId !== availabilityRequestId) {
            return;
        }

        resetAvailabilityState({ preserveMessage: true });
        showBookingMessage(error.message || 'Ошибка при загрузке свободных столов.', 'error');
    }
}

function scheduleAutoLoadAvailability() {
    clearTimeout(autoLoadTimer);
    autoLoadTimer = setTimeout(() => {
        loadAvailability({ silent: true });
    }, 250);
}

function toggleTableSelection(tableId) {
    if (!availabilityLoaded) {
        showBookingMessage('Подождите завершения загрузки доступности столов.', 'info');
        return;
    }

    if (occupiedTableIds.has(tableId)) {
        showBookingMessage('Этот стол уже занят на выбранный интервал.', 'error');
        return;
    }

    const existingIndex = selectedTableIds.indexOf(tableId);

    if (existingIndex >= 0) {
        selectedTableIds.splice(existingIndex, 1);
    } else {
        if (selectedTableIds.length >= MAX_TABLES_PER_RESERVATION) {
            showBookingMessage('Можно выбрать не более двух столов. Для большей брони свяжитесь с рестораном по телефону.', 'error');
            return;
        }

        selectedTableIds.push(tableId);
    }

    syncTableSelectionClasses();
    renderSelectedTables();

    if (selectedTableIds.length > 0) {
        showBookingMessage(`Выбрано столов: ${selectedTableIds.length}.`, 'info');
    } else {
        showBookingMessage('Выберите один или два свободных стола.', 'info');
    }
}

async function createBooking() {
    if (!isAuthenticated) {
        window.location.href = loginUrl;
        return;
    }

    if (!availabilityLoaded) {
        showBookingMessage('Сначала дождитесь загрузки свободных столов.', 'error');
        return;
    }

    if (selectedTableIds.length === 0) {
        showBookingMessage('Сначала выберите хотя бы один стол.', 'error');
        return;
    }

    const payload = {
        date: getSelectedBookingDate(),
        time_start: getSelectedBookingTime(),
        duration_minutes: getSelectedBookingDuration(),
        table_ids: selectedTableIds,
        comment: bookingComment?.value?.trim() || ''
    };

    createBookingBtn.disabled = true;
    checkAvailabilityBtn.disabled = true;
    showBookingMessage('Создаём бронирование...', 'info');

    try {
        const response = await fetch('/booking/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            if (response.status === 401) {
                window.location.href = loginUrl;
                return;
            }

            if (response.status === 409 && Array.isArray(data.occupied_table_ids)) {
                await loadAvailability({ silent: true });
            }

            throw new Error(data.error || 'Не удалось создать бронирование.');
        }

        selectedTableIds = [];
        renderSelectedTables();
        syncTableSelectionClasses();

        if (bookingComment) {
            bookingComment.value = '';
        }

        await loadAvailability({ silent: true });
        showBookingMessage('Бронирование успешно создано. Оно уже доступно в личном кабинете.', 'success');
    } catch (error) {
        showBookingMessage(error.message || 'Ошибка при создании бронирования.', 'error');
    } finally {
        updateCreateBookingButtonState();
        checkAvailabilityBtn.disabled = false;
    }
}

tables.forEach((table) => {
    const tableId = table.dataset.tableId;

    table.addEventListener('mouseenter', async (e) => {
        clearTimeout(hideTooltipTimer);

        try {
            const res = await fetch(`/api/table/${tableId}`);
            if (!res.ok) throw new Error('Table not found');

            const data = await res.json();
            currentTableData = data;

            const isUnavailable = occupiedTableIds.has(Number(tableId));
            const availabilityText = availabilityLoaded
                ? (isUnavailable ? '\nСтол занят на выбранный интервал.' : '\nСтол доступен на выбранный интервал.')
                : '';

            title.textContent = `Номер стола: ${data.number}`;
            tooltipContent.textContent = `Максимальное количество человек: ${data.seats}\n${data.description || ''}${availabilityText}`;

            if (data.image) {
                tooltipImg.src = `/static/${data.image}`;
                tooltipImg.alt = `Стол ${data.number}`;
                tooltipImg.style.display = 'block';
            } else {
                tooltipImg.src = '';
                tooltipImg.alt = '';
                tooltipImg.style.display = 'none';
            }

            if (data.image_panorama) {
                openPanoramaBtn.style.display = 'inline-flex';
            } else {
                openPanoramaBtn.style.display = 'none';
            }

            setTooltipPosition(e.pageX, e.pageY);
            showTooltip();
        } catch (err) {
            console.error(err);
        }
    });

    table.addEventListener('mousemove', (e) => {
        setTooltipPosition(e.pageX, e.pageY);
    });

    table.addEventListener('mouseleave', () => {
        hideTooltipWithDelay();
    });

    table.addEventListener('click', () => {
        toggleTableSelection(Number(table.dataset.tableId));
    });
});

tooltip.addEventListener('mouseenter', () => {
    clearTimeout(hideTooltipTimer);
});

tooltip.addEventListener('mouseleave', () => {
    hideTooltipWithDelay();
});

openPanoramaBtn.addEventListener('click', () => {
    if (!currentTableData || !currentTableData.image_panorama) return;

    panoramaTitle.textContent = `Панорама стола ${currentTableData.number}`;
    panoramaImg.src = `/static/${currentTableData.image_panorama}`;
    panoramaImg.alt = `Панорама стола ${currentTableData.number}`;

    panoramaModal.classList.add('is-open');
    document.body.classList.add('modal-open');

    panoramaViewer.scrollLeft = 0;
    panoramaViewer.scrollTop = 0;

    hideTooltipNow();
});

closePanoramaBtn.addEventListener('click', closePanorama);
panoramaBackdrop.addEventListener('click', closePanorama);

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closePanorama();
    }
});

function closePanorama() {
    panoramaModal.classList.remove('is-open');
    document.body.classList.remove('modal-open');
    panoramaImg.src = '';
    panoramaViewer.scrollLeft = 0;
    panoramaViewer.scrollTop = 0;
}

panoramaImg.addEventListener('load', () => {
    const maxScrollTop = panoramaViewer.scrollHeight - panoramaViewer.clientHeight;
    if (maxScrollTop > 0) {
        panoramaViewer.scrollTop = maxScrollTop / 2;
    } else {
        panoramaViewer.scrollTop = 0;
    }
});

panoramaViewer.addEventListener('mousedown', (e) => {
    isDragging = true;
    panoramaViewer.classList.add('is-dragging');

    startX = e.pageX;
    startY = e.pageY;
    startScrollLeft = panoramaViewer.scrollLeft;
    startScrollTop = panoramaViewer.scrollTop;
});

window.addEventListener('mouseup', () => {
    isDragging = false;
    panoramaViewer.classList.remove('is-dragging');
});

panoramaViewer.addEventListener('mouseleave', () => {
    panoramaViewer.classList.remove('is-dragging');
});

panoramaViewer.addEventListener('mousemove', (e) => {
    if (!isDragging) return;

    e.preventDefault();

    const dx = (e.pageX - startX) * 1.5;
    const dy = (e.pageY - startY) * 1.5;

    panoramaViewer.scrollLeft = startScrollLeft - dx;
    panoramaViewer.scrollTop = startScrollTop - dy;
});

panoramaViewer.addEventListener('touchstart', (e) => {
    touchStartX = e.touches[0].pageX;
    touchStartY = e.touches[0].pageY;
    touchStartScrollLeft = panoramaViewer.scrollLeft;
    touchStartScrollTop = panoramaViewer.scrollTop;
}, { passive: true });

panoramaViewer.addEventListener('touchmove', (e) => {
    const touchX = e.touches[0].pageX;
    const touchY = e.touches[0].pageY;

    const dx = (touchX - touchStartX) * 1.2;
    const dy = (touchY - touchStartY) * 1.2;

    panoramaViewer.scrollLeft = touchStartScrollLeft - dx;
    panoramaViewer.scrollTop = touchStartScrollTop - dy;
}, { passive: true });

if (selectedTablesBox) {
    selectedTablesBox.addEventListener('click', (event) => {
        const removeButton = event.target.closest('[data-remove-table-id]');
        if (!removeButton) return;

        const tableId = Number(removeButton.dataset.removeTableId);
        selectedTableIds = selectedTableIds.filter((id) => id !== tableId);
        syncTableSelectionClasses();
        renderSelectedTables();

        if (selectedTableIds.length === 0) {
            showBookingMessage('Выберите один или два свободных стола.', 'info');
        } else {
            showBookingMessage(`Выбрано столов: ${selectedTableIds.length}.`, 'info');
        }
    });
}

if (checkAvailabilityBtn) {
    checkAvailabilityBtn.addEventListener('click', () => {
        loadAvailability();
    });
}

if (createBookingBtn) {
    createBookingBtn.addEventListener('click', () => {
        createBooking();
    });
}

if (bookingDateInput) {
    bookingDateInput.addEventListener('change', () => {
        resetAvailabilityState({ preserveMessage: false, message: 'Дата изменена. Обновляем доступность столов...' });
        updateSummary();
        scheduleAutoLoadAvailability();
    });
}

if (bookingTimeSelect) {
    bookingTimeSelect.addEventListener('change', () => {
        populateDurationOptions();
        resetAvailabilityState({ preserveMessage: false, message: 'Время изменено. Обновляем доступность столов...' });
        updateSummary();
        scheduleAutoLoadAvailability();
    });
}

if (bookingDurationSelect) {
    bookingDurationSelect.addEventListener('change', () => {
        resetAvailabilityState({ preserveMessage: false, message: 'Длительность изменена. Обновляем доступность столов...' });
        updateSummary();
        scheduleAutoLoadAvailability();
    });
}

initializeBookingForm();
loadAvailability({ silent: true });