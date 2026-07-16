const API = '';
let currentPage = 1;
let totalPages = 1;
let searchTimer = null;

// --- Navigation ---
function showPage(name, el) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
    if (el) el.classList.add('active');
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
            fetch(API + '/api/stats'),
            fetch(API + '/api/price-trends'),
            fetch(API + '/api/brand-analysis'),
        ]);
        const stats = await statsRes.json();
        const trends = await trendsRes.json();
        const brands = await brandsRes.json();
        renderStats(stats);
        renderTrendChart(trends.trends);
        renderBrandBars(brands.brands.slice(0, 8));
    } catch (e) {
        console.error('Dashboard error:', e);
    }
}

function renderStats(s) {
    const grid = document.getElementById('stats-grid');
    grid.innerHTML = 
        '<div class="stat-card"><div class="label">Przedmioty</div><div class="value accent">' + s.total_items.toLocaleString() + '</div></div>' +
        '<div class="stat-card"><div class="label">Śr. cena</div><div class="value green">' + s.avg_price + ' zł</div></div>' +
        '<div class="stat-card"><div class="label">Min cena</div><div class="value yellow">' + s.min_price + ' zł</div></div>' +
        '<div class="stat-card"><div class="label">Max cena</div><div class="value">' + s.max_price + ' zł</div></div>' +
        '<div class="stat-card"><div class="label">Aktywne zapytania</div><div class="value accent">' + s.active_queries + '</div></div>' +
        '<div class="stat-card"><div class="label">Wszystkie zapytania</div><div class="value">' + s.total_queries + '</div></div>';
}

function renderTrendChart(trends) {
    const canvas = document.getElementById('trend-chart');
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth * 2;
    canvas.height = 400;
    ctx.scale(2, 2);
    const w = canvas.offsetWidth;
    const h = 200;
    const pad = { t: 20, r: 20, b: 40, l: 60 };
    ctx.clearRect(0, 0, w, h);
    if (!trends || trends.length === 0) {
        ctx.fillStyle = '#606078';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Brak danych do wyświetlenia', w / 2, h / 2);
        return;
    }
    const prices = trends.map(function(t) { return t.avg_price; });
    const counts = trends.map(function(t) { return t.count; });
    var maxP = Math.max.apply(null, prices) * 1.1;
    var minP = Math.min.apply(null, prices) * 0.9;
    var maxC = Math.max.apply(null, counts) * 1.1;
    var cW = w - pad.l - pad.r;
    var cH = h - pad.t - pad.b;
    ctx.strokeStyle = '#2e2e40';
    ctx.lineWidth = 0.5;
    for (var i = 0; i <= 4; i++) {
        var y = pad.t + (cH / 4) * i;
        ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w - pad.r, y); ctx.stroke();
        ctx.fillStyle = '#606078'; ctx.font = '11px sans-serif'; ctx.textAlign = 'right';
        var val = maxP - (maxP - minP) * (i / 4);
        ctx.fillText(val.toFixed(0) + 'zł', pad.l - 8, y + 4);
    }
    var barW = cW / trends.length * 0.6;
    var grad = ctx.createLinearGradient(0, 0, w, 0);
    grad.addColorStop(0, '#a855f7');
    grad.addColorStop(1, '#06b6d4');
    trends.forEach(function(t, i) {
        var x = pad.l + (cW / (trends.length - 1 || 1)) * i - barW / 2;
        var bH = (t.count / maxC) * cH;
        ctx.fillStyle = 'rgba(168,85,247,0.15)';
        ctx.fillRect(x, pad.t + cH - bH, barW, bH);
    });
    ctx.beginPath();
    var lineGrad = ctx.createLinearGradient(pad.l, 0, w - pad.r, 0);
    lineGrad.addColorStop(0, '#a855f7');
    lineGrad.addColorStop(1, '#06b6d4');
    ctx.strokeStyle = lineGrad;
    ctx.lineWidth = 2.5;
    ctx.shadowColor = 'rgba(168,85,247,0.5)';
    ctx.shadowBlur = 8;
    trends.forEach(function(t, i) {
        var x = pad.l + (cW / (trends.length - 1 || 1)) * i;
        var y = pad.t + cH - ((t.avg_price - minP) / (maxP - minP)) * cH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;
    trends.forEach(function(t, i) {
        var x = pad.l + (cW / (trends.length - 1 || 1)) * i;
        var y = pad.t + cH - ((t.avg_price - minP) / (maxP - minP)) * cH;
        ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#06b6d4'; ctx.fill();
    });
    ctx.fillStyle = '#606078'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
    trends.forEach(function(t, i) {
        var x = pad.l + (cW / (trends.length - 1 || 1)) * i;
        var d = t.date.substring(5);
        ctx.fillText(d, x, h - 10);
    });
}

function renderBrandBars(brands) {
    var el = document.getElementById('brand-bars');
    if (!brands || brands.length === 0) {
        el.innerHTML = '<div class="empty">Brak danych o markach</div>';
        return;
    }
    var max = Math.max.apply(null, brands.map(function(b) { return b.count; }));
    el.innerHTML = brands.map(function(b) {
        var pct = (b.count / max * 100).toFixed(0);
        return '<div class="brand-bar"><div class="bar-label"><span>' + b.brand + '</span><span>' + b.count + '</span></div><div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div></div>';
    }).join('');
}

// --- Items ---
async function loadItems() {
    var search = document.getElementById('item-search').value;
    var sort = document.getElementById('item-sort').value;
    try {
        var res = await fetch(API + '/api/items?search=' + encodeURIComponent(search) + '&sort=' + sort + '&page=' + currentPage);
        var data = await res.json();
        totalPages = data.pages;
        var grid = document.getElementById('items-grid');
        if (currentPage === 1) grid.innerHTML = '';
        if (data.items.length === 0 && currentPage === 1) {
            grid.innerHTML = '<div class="empty">Brak przedmiotów. Dodaj wyszukiwanie i uruchom bota.</div>';
            document.getElementById('load-more-btn').style.display = 'none';
            return;
        }
        data.items.forEach(function(item) {
            var tags = '';
            if (item.brand) tags += '<span class="tag">' + item.brand + '</span>';
            if (item.size) tags += '<span class="tag">' + item.size + '</span>';
            if (item.color) tags += '<span class="tag">' + item.color + '</span>';
            var img = item.image_url ? '<img class="item-img" src="' + item.image_url + '" loading="lazy" onerror="this.style.display=\'none\'">' : '';
            var html = '<div class="item-card">' + img +
                '<div class="item-top"><span class="item-title">' + (item.title || '') + '</span><span class="item-price">' + item.price + ' zł</span></div>' +
                '<div class="item-meta">' + tags + '</div>' +
                (item.url ? '<a class="item-link" href="' + item.url + '" target="_blank">🔗 Zobacz na Vinted →</a>' : '') +
                '</div>';
            grid.innerHTML += html;
        });
        document.getElementById('load-more-btn').style.display = currentPage < totalPages ? 'inline-flex' : 'none';
    } catch (e) {
        console.error('Items error:', e);
    }
}

function loadMore() {
    currentPage++;
    loadItems();
}

function debounceSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function() {
        currentPage = 1;
        loadItems();
    }, 300);
}

// --- Queries ---
async function loadQueries() {
    try {
        var res = await fetch(API + '/api/queries');
        var data = await res.json();
        var tbody = document.getElementById('queries-table');
        if (!data.queries.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty">Brak wyszukiwań. Dodaj pierwsze!</td></tr>';
            return;
        }
        tbody.innerHTML = data.queries.map(function(q) {
            var urlShort = q.url.length > 40 ? q.url.substring(0, 40) + '...' : q.url;
            var lastRun = q.last_run ? new Date(q.last_run).toLocaleString('pl-PL') : 'Nigdy';
            return '<tr>' +
                '<td><strong>' + q.name + '</strong></td>' +
                '<td style="max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;color:var(--t3)" title="' + q.url + '">' + urlShort + '</td>' +
                '<td><span class="btn-icon" onclick="toggleQuery(' + q.id + ')" style="color:' + (q.is_active ? 'var(--ok)' : 'var(--t3)') + '">' + (q.is_active ? '🟢' : '⚫') + '</span></td>' +
                '<td style="font-size:12px;color:var(--t2)">' + q.interval_minutes + ' min</td>' + '<td style="font-size:12px;color:' + (q.target_price ? 'var(--warn)' : 'var(--t3)') + ';font-weight:600">' + (q.target_price ? q.target_price + ' zł' : '—') + '</td>' +
                '<td><span class="toggle ' + (q.notify_empty ? 'on' : 'off') + '" onclick="toggleNotifyEmpty(' + q.id + ')">' + (q.notify_empty ? '🔔 Wł.' : '🔕 Wył.') + '</span></td>' +
                '<td><span class="btn-icon" onclick="deleteQuery(' + q.id + ')" style="color:var(--err)">🗑️</span></td>' +
                '</tr>';
        }).join('');
    } catch (e) {
        console.error('Queries error:', e);
    }
}

function showAddQueryModal() {
    document.getElementById('add-query-modal').classList.add('active');
}

function closeModal() {
    document.getElementById('add-query-modal').classList.remove('active');
}

async function addQuery() {
    var name = document.getElementById('q-name').value.trim();
    var url = document.getElementById('q-url').value.trim();
    var interval = document.getElementById('q-interval').value;
    var targetPrice = document.getElementById('q-target-price').value;
    if (!name || !url) { showToast('Wypełnij wszystkie pola', 'error'); return; }
    try {
        var res = await fetch(API + '/api/queries?name=' + encodeURIComponent(name) + '&url=' + encodeURIComponent(url) + '&interval=' + interval + (targetPrice ? '&target_price=' + targetPrice : ''), { method: 'POST' });
        if (res.ok) {
            showToast('Dodano wyszukiwanie!');
            closeModal();
            loadQueries();
        } else {
            var err = await res.json();
            showToast(err.detail || 'Błąd', 'error');
        }
    } catch (e) { showToast('Błąd połączenia', 'error'); }
}

async function toggleQuery(id) {
    await fetch(API + '/api/queries/' + id + '/toggle', { method: 'POST' });
    loadQueries();
}

async function deleteQuery(id) {
    if (!confirm('Na pewno usunąć?')) return;
    await fetch(API + '/api/queries/' + id, { method: 'DELETE' });
    showToast('Usunięto');
    loadQueries();
}

async function toggleNotifyEmpty(id) {
    await fetch(API + '/api/queries/' + id + '/toggle-notify', { method: 'POST' });
    loadQueries();
}

// --- Analysis ---
async function loadAnalysis() {
    try {
        var res = await fetch(API + '/api/brand-analysis');
        var data = await res.json();
        var tbody = document.getElementById('brand-table');
        if (!data.brands.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty">Brak danych. Uruchom bota aby zebrać dane.</td></tr>';
            return;
        }
        tbody.innerHTML = data.brands.map(function(b) {
            return '<tr><td><strong>' + b.brand + '</strong></td><td>' + b.count + '</td><td style="color:var(--accent);font-weight:600">' + b.avg_price + ' zł</td><td style="color:var(--ok)">' + b.min_price + ' zł</td><td style="color:var(--warn)">' + b.max_price + ' zł</td></tr>';
        }).join('');
    } catch (e) { console.error('Analysis error:', e); }
}

// --- Toast ---
function showToast(msg, type) {
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast ' + (type || '') + ' show';
    setTimeout(function() { t.classList.remove('show'); }, 3000);
}

// --- Vinted Login ---
function showLoginModal() { document.getElementById('login-modal').classList.add('active'); }
function closeLoginModal() { document.getElementById('login-modal').classList.remove('active'); }

async function vintedLogin() {
    var email = document.getElementById('login-email').value.trim();
    var pass = document.getElementById('login-password').value;
    var err = document.getElementById('login-error');
    if (!email || !pass) { err.textContent = 'Wypełnij pola'; return; }
    err.textContent = '';
    try {
        var r = await fetch('/api/vinted/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email: email, password: pass}) });
        var d = await r.json();
        if (r.ok) { showToast('Zalogowano!'); closeLoginModal(); checkVintedStatus(); }
        else { err.textContent = d.error || 'Błąd'; }
    } catch (e) { err.textContent = 'Błąd połączenia'; }
}

async function modalLogin() {
    var email = document.getElementById('modal-email').value.trim();
    var pass = document.getElementById('modal-password').value;
    var err = document.getElementById('modal-login-error');
    if (!email || !pass) { err.textContent = 'Wypełnij pola'; return; }
    err.textContent = '';
    try {
        var r = await fetch('/api/vinted/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email: email, password: pass}) });
        var d = await r.json();
        if (r.ok) { showToast('Zalogowano!'); closeLoginModal(); checkVintedStatus(); }
        else { err.textContent = d.error || 'Błąd'; }
    } catch (e) { err.textContent = 'Błąd połączenia'; }
}

async function checkVintedStatus() {
    try {
        var r = await fetch('/api/vinted/status');
        var d = await r.json();
        var el = document.getElementById('vinted-status-text');
        var acc = document.getElementById('account-status');
        if (d.status === 'logged_in') {
            if (el) { el.innerHTML = '✅ ' + d.email; el.style.color = 'var(--ok)'; }
            if (acc) { acc.innerHTML = '✅ Zalogowano jako ' + d.email; acc.style.color = 'var(--ok)'; }
        } else {
            if (el) { el.innerHTML = '❌ Nie zalogowano'; el.style.color = 'var(--err)'; }
            if (acc) { acc.innerHTML = '❌ Nie zalogowano'; acc.style.color = 'var(--err)'; }
        }
    } catch (e) {}
}

async function vintedLogout() {
    if (!confirm('Wylogować?')) return;
    await fetch('/api/vinted/logout', { method: 'POST' });
    showToast('Wylogowano');
    checkVintedStatus();
}

// --- Init ---
loadDashboard();
checkVintedStatus();
