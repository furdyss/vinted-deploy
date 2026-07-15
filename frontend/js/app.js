const API = '';
let currentPage = 1;
let totalPages = 1;
let searchTimer = null;

// --- Navigation ---
function showPage(name) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById(`page-${name}`).classList.add('active');
    event.currentTarget.classList.add('active');
    if (window.innerWidth < 768) toggleSidebar();
    if (name === 'dashboard') loadDashboard();
    if (name === 'items') { currentPage = 1; loadItems(); }
    if (name === 'queries') loadQueries();
    if (name === 'analysis') loadAnalysis();
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

// --- Dashboard ---
async function loadDashboard() {
    try {
        const [statsRes, trendsRes, brandsRes] = await Promise.all([
            fetch(`${API}/api/stats`),
            fetch(`${API}/api/price-trends`),
            fetch(`${API}/api/brand-analysis`),
        ]);
        const stats = await statsRes.json();
        const trends = await trendsRes.json();
        const brands = await brandsRes.json();
        renderStats(stats);
        renderTrendChart(trends.trends);
        renderBrandBars(brands.brands.slice(0, 8));
    } catch (e) {
        console.error('Dashboard load error:', e);
    }
}

function renderStats(s) {
    const grid = document.getElementById('stats-grid');
    grid.innerHTML = `
        <div class="stat-card"><div class="label">Przedmioty</div><div class="value accent">${s.total_items.toLocaleString()}</div></div>
        <div class="stat-card"><div class="label">Śr. cena</div><div class="value green">${s.avg_price} €</div></div>
        <div class="stat-card"><div class="label">Min cena</div><div class="value yellow">${s.min_price} €</div></div>
        <div class="stat-card"><div class="label">Max cena</div><div class="value">${s.max_price} €</div></div>
        <div class="stat-card"><div class="label">Aktywne zapytania</div><div class="value accent">${s.active_queries}</div></div>
        <div class="stat-card"><div class="label">Wszystkie zapytania</div><div class="value">${s.total_queries}</div></div>
    `;
}

function renderTrendChart(trends) {
    const canvas = document.getElementById('trend-chart');
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth * 2;
    canvas.height = 400;
    ctx.scale(2, 2);

    const w = canvas.offsetWidth;
    const h = 200;
    const padding = { top: 20, right: 20, bottom: 40, left: 60 };

    ctx.clearRect(0, 0, w, h);

    if (!trends || trends.length === 0) {
        ctx.fillStyle = '#606078';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Brak danych do wyświetlenia', w / 2, h / 2);
        return;
    }

    const prices = trends.map(t => t.avg_price);
    const counts = trends.map(t => t.count);
    const maxPrice = Math.max(...prices) * 1.1;
    const minPrice = Math.min(...prices) * 0.9;
    const maxCount = Math.max(...counts) * 1.1;

    const chartW = w - padding.left - padding.right;
    const chartH = h - padding.top - padding.bottom;

    // Grid
    ctx.strokeStyle = '#2e2e40';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
        const y = padding.top + (chartH / 4) * i;
        ctx.beginPath(); ctx.moveTo(padding.left, y); ctx.lineTo(w - padding.right, y); ctx.stroke();
        ctx.fillStyle = '#606078'; ctx.font = '11px sans-serif'; ctx.textAlign = 'right';
        const val = maxPrice - (maxPrice - minPrice) * (i / 4);
        ctx.fillText(val.toFixed(0) + '€', padding.left - 8, y + 4);
    }

    // Bars (count)
    const barWidth = chartW / trends.length * 0.6;
    trends.forEach((t, i) => {
        const x = padding.left + (chartW / (trends.length - 1 || 1)) * i - barWidth / 2;
        const barH = (t.count / maxCount) * chartH;
        ctx.fillStyle = 'rgba(124, 92, 255, 0.15)';
        ctx.fillRect(x, padding.top + chartH - barH, barWidth, barH);
    });

    // Line (price)
    ctx.beginPath();
    ctx.strokeStyle = '#7c5cff';
    ctx.lineWidth = 2;
    ctx.shadowColor = 'rgba(124, 92, 255, 0.5)';
    ctx.shadowBlur = 8;
    trends.forEach((t, i) => {
        const x = padding.left + (chartW / (trends.length - 1 || 1)) * i;
        const y = padding.top + chartH - ((t.avg_price - minPrice) / (maxPrice - minPrice)) * chartH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Dots
    trends.forEach((t, i) => {
        const x = padding.left + (chartW / (trends.length - 1 || 1)) * i;
        const y = padding.top + chartH - ((t.avg_price - minPrice) / (maxPrice - minPrice)) * chartH;
        ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#7c5cff'; ctx.fill();
    });

    // X labels
    ctx.fillStyle = '#606078'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(trends.length / 8));
    trends.forEach((t, i) => {
        if (i % step === 0 || i === trends.length - 1) {
            const x = padding.left + (chartW / (trends.length - 1 || 1)) * i;
            const label = t.date.slice(5);
            ctx.fillText(label, x, h - padding.bottom + 20);
        }
    });
}

function renderBrandBars(brands) {
    const container = document.getElementById('brand-bars');
    if (!brands.length) { container.innerHTML = '<div class="empty-state"><p>Brak danych o markach</p></div>'; return; }
    const maxCount = Math.max(...brands.map(b => b.count));
    container.innerHTML = brands.map(b => `
        <div class="brand-bar">
            <span class="name">${b.brand}</span>
            <div class="bar"><div class="bar-fill" style="width:${(b.count / maxCount * 100).toFixed(1)}%">
                <span class="count">${b.count}</span>
            </div></div>
            <span style="min-width:50px;text-align:right;color:var(--accent);font-weight:600;font-size:13px">${b.avg_price}€</span>
        </div>
    `).join('');
}

// --- Items ---
async function loadItems(reset = true) {
    if (reset) currentPage = 1;
    const search = document.getElementById('item-search').value;
    const sort = document.getElementById('item-sort').value;
    try {
        const res = await fetch(`${API}/api/items?search=${encodeURIComponent(search)}&sort=${sort}&page=${currentPage}&per_page=24`);
        const data = await res.json();
        totalPages = data.pages;
        const grid = document.getElementById('items-grid');
        if (reset) grid.innerHTML = '';
        if (data.items.length === 0 && reset) {
            grid.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg><p>Brak przedmiotów. Dodaj wyszukiwanie i uruchom fetch.</p></div>';
            document.getElementById('load-more-btn').style.display = 'none';
            return;
        }
        grid.innerHTML += data.items.map(item => `
            <a class="item-card" href="${item.url}" target="_blank" style="text-decoration:none;color:inherit">
                <div class="image-wrap">
                    ${item.image_url ? `<img src="${item.image_url}" alt="${item.title}" loading="lazy">` : '<svg viewBox="0 0 24 24" fill="none" stroke="#606078" stroke-width="1" width="48"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>'}
                </div>
                <div class="info">
                    <div class="title">${item.title || 'Bez tytułu'}</div>
                    <div class="meta">
                        <span class="price">${item.price} ${item.currency || '€'}</span>
                    </div>
                    <div class="details">
                        ${item.brand ? `<span class="tag brand">${item.brand}</span>` : ''}
                        ${item.size ? `<span class="tag size">${item.size}</span>` : ''}
                        ${item.condition ? `<span class="tag">${item.condition}</span>` : ''}
                    </div>
                </div>
            </a>
        `).join('');
        document.getElementById('load-more-btn').style.display = currentPage < totalPages ? 'inline-flex' : 'none';
    } catch (e) {
        console.error('Items load error:', e);
    }
}

function loadMore() { currentPage++; loadItems(false); }

function debounceSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadItems(), 400);
}

// --- Queries ---
async function loadQueries() {
    try {
        const res = await fetch(`${API}/api/queries`);
        const data = await res.json();
        const tbody = document.getElementById('queries-table');
        if (!data.queries.length) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-muted)">Brak zapisanych wyszukiwań</td></tr>';
            return;
        }
        tbody.innerHTML = data.queries.map(q => `
            <tr>
                <td><strong>${q.name}</strong></td>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;color:var(--text-muted)">${q.url}</td>
                <td><span class="${q.is_active ? 'status-active' : 'status-inactive'}">${q.is_active ? '● Aktywne' : '● Nieaktywne'}</span></td>
                <td>${q.interval_minutes} min</td>
                <td>${q.last_run ? new Date(q.last_run).toLocaleString('pl-PL') : 'Nigdy'}</td>
                <td>
                    <div style="display:flex;gap:6px;flex-wrap:wrap">
                        <button class="btn btn-primary btn-sm" onclick="fetchNow(${q.id})">⚡ Fetch</button>
                        <button class="btn btn-secondary btn-sm" onclick="toggleQuery(${q.id})">🔄</button>
                        <button class="btn btn-danger btn-sm" onclick="deleteQuery(${q.id})">✕</button>
                    </div>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        console.error('Queries load error:', e);
    }
}

function showAddQueryModal() {
    document.getElementById('add-query-modal').classList.add('active');
}

function closeModal() {
    document.getElementById('add-query-modal').classList.remove('active');
}

async function addQuery() {
    const name = document.getElementById('q-name').value.trim();
    const url = document.getElementById('q-url').value.trim();
    const interval = document.getElementById('q-interval').value;
    if (!name || !url) { showToast('Wypełnij wszystkie pola', 'error'); return; }
    try {
        const res = await fetch(`${API}/api/queries?name=${encodeURIComponent(name)}&url=${encodeURIComponent(url)}&interval=${interval}`, { method: 'POST' });
        if (res.ok) {
            showToast('Dodano wyszukiwanie!');
            closeModal();
            loadQueries();
        } else {
            const err = await res.json();
            showToast(err.detail || 'Błąd', 'error');
        }
    } catch (e) { showToast('Błąd połączenia', 'error'); }
}

async function fetchNow(id) {
    showToast('Pobieranie danych...');
    try {
        const res = await fetch(`${API}/api/fetch/${id}`, { method: 'POST' });
        const data = await res.json();
        if (data.error) { showToast(`Błąd: ${data.error}`, 'error'); }
        else { showToast(`Pobrano ${data.new_items} nowych z ${data.total_found} znalezionych`); loadQueries(); }
    } catch (e) { showToast('Błąd połączenia', 'error'); }
}

async function toggleQuery(id) {
    await fetch(`${API}/api/queries/${id}/toggle`, { method: 'POST' });
    loadQueries();
}

async function deleteQuery(id) {
    if (!confirm('Na pewno usunąć?')) return;
    await fetch(`${API}/api/queries/${id}`, { method: 'DELETE' });
    showToast('Usunięto');
    loadQueries();
}

// --- Analysis ---
async function loadAnalysis() {
    try {
        const res = await fetch(`${API}/api/brand-analysis`);
        const data = await res.json();
        const tbody = document.getElementById('brand-table');
        if (!data.brands.length) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-muted)">Brak danych. Uruchom fetch aby zebrać dane.</td></tr>';
            return;
        }
        tbody.innerHTML = data.brands.map(b => `
            <tr>
                <td><strong>${b.brand}</strong></td>
                <td>${b.count}</td>
                <td style="color:var(--accent);font-weight:600">${b.avg_price} €</td>
                <td style="color:var(--success)">${b.min_price} €</td>
                <td style="color:var(--warning)">${b.max_price} €</td>
            </tr>
        `).join('');
    } catch (e) { console.error('Analysis load error:', e); }
}

// --- Toast ---
function showToast(msg, type = 'success') {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = `toast ${type} show`;
    setTimeout(() => t.classList.remove('show'), 3000);
}

// --- Init ---
loadDashboard();
