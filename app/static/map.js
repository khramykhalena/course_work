
function setupAdminModeButton() {
    const button = document.getElementById('adminModeButton');
    if (!button) return;

    const isAdminMode = sessionStorage.getItem('adminMode') === '1' && !!sessionStorage.getItem('adminToken');

    if (isAdminMode) {
        button.textContent = 'Режим пользователя';
        button.href = '/';
        button.classList.add('user-mode-button');
        button.addEventListener('click', (event) => {
            event.preventDefault();
            sessionStorage.removeItem('adminMode');
            sessionStorage.removeItem('adminToken');
            window.location.href = '/';
        });
    } else {
        button.textContent = 'Вход администратора';
        button.href = '/admin';
    }
}

setupAdminModeButton();

function isAdminModeActive() {
    return sessionStorage.getItem('adminMode') === '1' && !!sessionStorage.getItem('adminToken');
}

function getApiHeaders() {
    const token = sessionStorage.getItem('adminToken');
    if (sessionStorage.getItem('adminMode') === '1' && token) {
        return {Authorization: 'Bearer ' + token};
    }
    return {};
}

async function apiFetch(url) {
    return fetch(url, {headers: getApiHeaders()});
}

const map = L.map('map').setView([55.751244, 37.618423], 10);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap'
}).addTo(map);

let markersLayer = L.layerGroup().addTo(map);
let currentItems = [];

function addOptions(selectId, values) {
    const select = document.getElementById(selectId);
    select.innerHTML = '<option value="">Все</option>';
    values.forEach(value => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
    });
}

async function loadFilterValues() {
    const response = await apiFetch('/api/filter-values');
    if (!response.ok) {
        document.getElementById('counter').textContent = 'Не удалось загрузить фильтры';
        return;
    }
    const data = await response.json();
    addOptions('status', data.status || []);
    addOptions('category', data.category || []);
    addOptions('objectGroup', data.object_group || []);
    addOptions('objectName', data.object_name || []);
}

function getFiltersQuery() {
    const params = new URLSearchParams();

    const values = {
        date_from: document.getElementById('dateFrom').value,
        date_to: document.getElementById('dateTo').value,
        status: document.getElementById('status').value,
        category: document.getElementById('category').value,
        object_group: document.getElementById('objectGroup').value,
        object_name: document.getElementById('objectName').value,
    };

    Object.entries(values).forEach(([key, value]) => {
        if (value) params.append(key, value);
    });

    return params.toString();
}

async function loadViolations() {
    const query = getFiltersQuery();
    const response = await apiFetch('/api/violations' + (query ? '?' + query : ''));
    if (!response.ok) {
        document.getElementById('counter').textContent = 'Не удалось загрузить данные';
        return;
    }

    const data = await response.json();
    currentItems = data.items;
    document.getElementById('counter').textContent = 'Найдено: ' + data.count;

    drawMarkers(data.items);
    drawList(data.items);
}

function drawMarkers(items) {
    markersLayer.clearLayers();

    const bounds = [];
    items.forEach(item => {
        const marker = L.marker([item.latitude, item.longitude]);
        marker.on('click', () => showViolationDetails(item.id, marker));
        marker.bindPopup('<b>ID задачи:</b> ' + item.task_id + '<br><b>Статус:</b> ' + (item.status || '-'));
        marker.addTo(markersLayer);
        bounds.push([item.latitude, item.longitude]);
    });

    if (bounds.length > 0) {
        map.fitBounds(bounds, {padding: [30, 30]});
    }
}

function drawList(items) {
    const list = document.getElementById('violationList');
    list.innerHTML = '';

    items.slice(0, 100).forEach(item => {
        const div = document.createElement('div');
        div.className = 'violation-item';
        div.innerHTML = '<b>' + item.task_id + '</b><br>' +
            '<span>' + (item.status || 'Без статуса') + '</span><br>' +
            '<small>' + (item.assigned_at || '') + '</small>';
        div.onclick = () => {
            map.setView([item.latitude, item.longitude], 16);
            showViolationDetails(item.id);
        };
        list.appendChild(div);
    });

    if (items.length > 100) {
        const note = document.createElement('p');
        note.textContent = 'В списке показаны первые 100 записей. На карте отображаются все найденные точки.';
        list.appendChild(note);
    }
}

async function showViolationDetails(id, marker = null) {
    const response = await apiFetch('/api/violation/' + id);
    if (!response.ok) return;

    const item = await response.json();
    const raw = JSON.parse(item.raw_json || '{}');

    let html = '<h3>Карточка нарушения</h3>';
    html += '<div class="detail-row"><b>ID задачи</b>' + item.task_id + '</div>';
    html += '<div class="detail-row"><b>Статус</b>' + (item.status || '-') + '</div>';
    html += '<div class="detail-row"><b>Дата назначения</b>' + (item.assigned_at || '-') + '</div>';
    html += '<div class="detail-row"><b>Координаты</b>' + item.latitude + ', ' + item.longitude + '</div>';

    Object.entries(raw).forEach(([key, value]) => {
        if (value === null || value === '') return;
        const safeValue = String(value);
        const looksLikeLink = safeValue.startsWith('http://') || safeValue.startsWith('https://');
        html += '<div class="detail-row"><b>' + key + '</b>' +
            (looksLikeLink ? '<a href="' + safeValue + '" target="_blank">Открыть ссылку</a>' : safeValue) +
            '</div>';
    });

    if (marker) {
        marker.bindPopup(html, {maxWidth: 420}).openPopup();
    } else {
        L.popup({maxWidth: 420})
            .setLatLng([item.latitude, item.longitude])
            .setContent(html)
            .openOn(map);
    }
}

function resetFilters() {
    ['dateFrom', 'dateTo', 'status', 'category', 'objectGroup', 'objectName'].forEach(id => {
        document.getElementById(id).value = '';
    });
    loadViolations();
}

loadFilterValues().then(loadViolations);
