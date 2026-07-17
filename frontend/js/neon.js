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
    if (name === 'sellers') loadSellers();
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
            var searchQ = encodeURIComponent((item.brand || '') + ' ' + (item.title || ''));
            var compareHtml = '<div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">';
            compareHtml += '<a class="item-link" href="https://www.vinted.pl/search?search_text=' + searchQ + '" target="_blank" style="font-size:11px">🔍 Vinted</a>';
            compareHtml += '<a class="item-link" href="https://allegro.pl/listing?string=' + searchQ + '" target="_blank" style="font-size:11px;color:#f59e0b">🛒 Allegro</a>';
            compareHtml += '<a class="item-link" href="https://www.olx.pl/oferty/q-' + searchQ.replace(/%20/g, '-') + '" target="_blank" style="font-size:11px;color:#a855f7">📦 OLX</a>';
            if (item.competitor_price) { compareHtml += '<span style="font-size:11px;color:#06b6d4;font-weight:600">vs ' + item.competitor_price + ' zł</span>'; }
            compareHtml += '</div>';
            var linkHtml = item.url ? '<a class="item-link" href="' + item.url + '" target="_blank">🔗 Zobacz na Vinted →</a>' : '';
            var html = '<div class="item-card">' + img +
                '<div class="item-top"><span class="item-title">' + (item.title || '') + '</span><span class="item-price">' + item.price + ' zł</span></div>' +
                '<div class="item-meta">' + tags + '</div>' +
                linkHtml + compareHtml +
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


// --- Price History ---
function closePriceModal() { document.getElementById('price-modal').classList.remove('active'); }

async function showPriceHistory(vintedId, title) {
    document.getElementById('price-modal-title').textContent = '💰 ' + (title || 'Historia cen');
    document.getElementById('price-modal').classList.add('active');
    
    try {
        var res = await fetch(API + '/api/price-history/' + vintedId);
        var data = await res.json();
        var history = data.history || [];
        var info = document.getElementById('price-history-info');
        
        if (history.length === 0) {
            info.innerHTML = 'Brak historii cen dla tego przedmiotu.';
            var ctx = document.getElementById('price-history-chart').getContext('2d');
            ctx.clearRect(0, 0, 350, 200);
            return;
        }
        
        var prices = history.map(function(h) { return h.price; });
        var min = Math.min.apply(null, prices);
        var max = Math.max.apply(null, prices);
        var avg = (prices.reduce(function(a, b) { return a + b; }, 0) / prices.length).toFixed(2);
        
        info.innerHTML = '<strong>Cena aktualna:</strong> ' + prices[prices.length - 1] + ' zł<br>' +
            '<strong>Najniższa:</strong> ' + min + ' zł<br>' +
            '<strong>Najwyższa:</strong> ' + max + ' zł<br>' +
            '<strong>Średnia:</strong> ' + avg + ' zł<br>' +
            '<strong>Pomiarów:</strong> ' + history.length;
        
        // Draw chart
        var canvas = document.getElementById('price-history-chart');
        var ctx = canvas.getContext('2d');
        canvas.width = canvas.offsetWidth * 2;
        canvas.height = 400;
        ctx.scale(2, 2);
        var w = canvas.offsetWidth;
        var h = 200;
        var pad = { t: 20, r: 20, b: 30, l: 50 };
        ctx.clearRect(0, 0, w, h);
        
        var cW = w - pad.l - pad.r;
        var cH = h - pad.t - pad.b;
        var range = max - min || 1;
        
        // Grid
        ctx.strokeStyle = '#2e2e40';
        ctx.lineWidth = 0.5;
        for (var i = 0; i <= 3; i++) {
            var y = pad.t + (cH / 3) * i;
            ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w - pad.r, y); ctx.stroke();
            ctx.fillStyle = '#606078'; ctx.font = '10px sans-serif'; ctx.textAlign = 'right';
            ctx.fillText((max - range * (i / 3)).toFixed(0) + 'zł', pad.l - 5, y + 3);
        }
        
        // Line
        if (history.length > 1) {
            var grad = ctx.createLinearGradient(pad.l, 0, w - pad.r, 0);
            grad.addColorStop(0, '#a855f7');
            grad.addColorStop(1, '#06b6d4');
            ctx.beginPath();
            ctx.strokeStyle = grad;
            ctx.lineWidth = 2;
            history.forEach(function(h, i) {
                var x = pad.l + (cW / (history.length - 1)) * i;
                var y = pad.t + cH - ((h.price - min) / range) * cH;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.stroke();
        }
        
        // Dots
        history.forEach(function(h, i) {
            var x = pad.l + (cW / Math.max(history.length - 1, 1)) * i;
            var y = pad.t + cH - ((h.price - min) / range) * cH;
            ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fillStyle = '#06b6d4'; ctx.fill();
        });
        
    } catch (e) {
        document.getElementById('price-history-info').innerHTML = 'Błąd ładowania historii.';
    }
}


// --- Sellers ---
async function loadSellers() {
    try {
        var res = await fetch(API + '/api/sellers');
        var data = await res.json();
        var el = document.getElementById('sellers-list');
        if (!data.sellers.length) {
            el.innerHTML = '<div class="empty">Brak śledzonych sprzedawców. Dodaj pierwszego!</div>';
            return;
        }
        el.innerHTML = data.sellers.map(function(s) {
            return '<div class="card" style="display:flex;justify-content:space-between;align-items:center;cursor:pointer" onclick="showSellerDetail(' + s.id + ', \'' + s.username + '\')">' +
                '<div><div style="font-weight:600;color:var(--accent)">' + s.username + '</div>' +
                '<div style="font-size:12px;color:var(--t3);margin-top:4px">' + s.last_item_count + ' ogłoszeń</div></div>' +
                '<div style="display:flex;gap:8px;align-items:center" onclick="event.stopPropagation()">' +
                '<span class="toggle ' + (s.is_active ? 'on' : 'off') + '" onclick="toggleSeller(' + s.id + ')">' + (s.is_active ? '🟢' : '⚫') + '</span>' +
                '<span class="btn-icon" onclick="deleteSeller(' + s.id + ')" style="color:var(--err)">🗑️</span>' +
                '</div></div>';
        }).join('');
    } catch (e) {
        console.error('Sellers error:', e);
    }
}

async function addSeller() {
    var username = document.getElementById('seller-username').value.trim();
    if (!username) { showToast('Wpisz nazwę sprzedawcy', 'error'); return; }
    try {
        var res = await fetch(API + '/api/sellers?username=' + encodeURIComponent(username), { method: 'POST' });
        if (res.ok) {
            showToast('Dodano sprzedawcę!');
            document.getElementById('seller-username').value = '';
            loadSellers();
        } else {
            var err = await res.json();
            showToast(err.detail || 'Błąd', 'error');
        }
    } catch (e) { showToast('Błąd połączenia', 'error'); }
}

async function toggleSeller(id) {
    await fetch(API + '/api/sellers/' + id + '/toggle', { method: 'POST' });
    loadSellers();
}

async function deleteSeller(id) {
    if (!confirm('Usunąć sprzedawcę?')) return;
    await fetch(API + '/api/sellers/' + id, { method: 'DELETE' });
    showToast('Usunięto');
    loadSellers();
}


// --- Seller Detail ---
function closeSellerModal() { document.getElementById('seller-modal').classList.remove('active'); }

async function showSellerDetail(sellerId, username) {
    document.getElementById('seller-modal-title').textContent = '👤 ' + username;
    document.getElementById('seller-modal').classList.add('active');
    document.getElementById('seller-modal-items').innerHTML = '<div class="empty">Ładowanie przedmiotów...</div>';
    document.getElementById('seller-modal-stats').innerHTML = '';
    
    try {
        var res = await fetch(API + '/api/sellers/' + sellerId + '/items');
        var data = await res.json();
        var items = data.items || [];
        var total = data.total || 0;
        
        // Stats - only from available items
        var available = items.filter(function(i) { return i.is_available !== false; });
        var prices = available.map(function(i) { return i.price; }).filter(function(p) { return p > 0; });
        var avg = prices.length ? (prices.reduce(function(a,b){return a+b},0) / prices.length).toFixed(2) : 0;
        var minP = prices.length ? Math.min.apply(null, prices) : 0;
        var maxP = prices.length ? Math.max.apply(null, prices) : 0;
        var sold = items.length - available.length;
        
        var brands = {};
        available.forEach(function(i) {
            if (i.brand) brands[i.brand] = (brands[i.brand] || 0) + 1;
        });
        var topBrand = Object.keys(brands).sort(function(a,b){return brands[b]-brands[a]})[0] || '—';
        
        document.getElementById('seller-modal-stats').innerHTML = 
            '<div class="stat-card"><div class="label">Aktywne</div><div class="value accent">' + total + '</div></div>' +
            '<div class="stat-card"><div class="label">Sprzedane</div><div class="value" style="color:#ef4444">' + sold + '</div></div>' +
            '<div class="stat-card"><div class="label">Śr. cena</div><div class="value green">' + avg + ' zł</div></div>' +
            '<div class="stat-card"><div class="label">Min</div><div class="value yellow">' + minP + ' zł</div></div>' +
            '<div class="stat-card"><div class="label">Max</div><div class="value">' + maxP + ' zł</div></div>' +
            '<div class="stat-card"><div class="label">Top marka</div><div class="value accent">' + topBrand + '</div></div>';
        
        // Items
        if (!items.length) {
            document.getElementById('seller-modal-items').innerHTML = '<div class="empty">Brak danych — bot dopiero zbiera informacje o tym sprzedawcy. Sprawdź ponownie za kilka minut.</div>';
            return;
        }
        
        document.getElementById('seller-modal-items').innerHTML = items.map(function(item) {
            var tags = '';
            if (item.brand) tags += '<span class="tag">' + item.brand + '</span>';
            if (item.is_available === false) tags += '<span class="tag" style="background:rgba(239,68,68,0.15);color:#ef4444">SPRZEDANE</span>';
            
            var img = item.photo ? '<img class="item-img" src="' + item.photo + '" loading="lazy" onerror="this.style.display=\'none\'">' : '';
            
            var priceHtml = '<span class="item-price">' + item.price + ' zł</span>';
            if (item.previous_price && item.previous_price !== item.price && item.previous_price > 0) {
                var diff = item.previous_price - item.price;
                var color = diff > 0 ? '#22c55e' : '#ef4444';
                var arrow = diff > 0 ? '📉' : '📈';
                priceHtml += '<div style="font-size:11px;color:' + color + ';margin-top:2px">' + arrow + 'Było: ' + item.previous_price + ' zł</div>';
            }
            
            var url = item.url || ('https://www.vinted.pl/items/' + item.vinted_id);
            var dateStr = item.first_seen ? new Date(item.first_seen).toLocaleDateString('pl-PL') : '';
            
            return '<div class="item-card" style="' + (item.is_available === false ? 'opacity:0.5' : '') + '">' + img +
                '<div class="item-top"><span class="item-title">' + (item.title || 'Brak tytułu') + '</span>' + priceHtml + '</div>' +
                '<div class="item-meta">' + tags + '</div>' +
                (dateStr ? '<div style="font-size:11px;color:var(--t3);margin-top:6px">📅 ' + dateStr + '</div>' : '') +
                '<a class="item-link" href="' + url + '" target="_blank">🔗 Zobacz na Vinted →</a>' +
                '</div>';
        }).join('');
        
    } catch (e) {
        document.getElementById('seller-modal-items').innerHTML = '<div class="empty">Błąd ładowania danych</div>';
    }
}
