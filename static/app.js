// State management
const state = {
    currentTab: 'products',
    products: [],
    naics: [],
    critical: [],
    currentSort: { field: 'china_deficit', order: 'desc' },
};

// Utility functions
const fmt = {
    number: (n) => {
        if (n === 0) return '0';
        if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B';
        if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
        if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(2) + 'K';
        return n.toFixed(0);
    },
    full: (n) => new Intl.NumberFormat('en-US').format(Math.round(n)),
    percent: (value, digits = 1) => {
        if (value === null || value === undefined) {
            return '—';
        }
        const num = Number(value);
        if (!Number.isFinite(num)) {
            return '—';
        }
        return (num * 100).toFixed(digits) + '%';
    },
};

// API calls
const api = {
    async getStats() {
        const res = await fetch('/api/stats');
        return await res.json();
    },
    async getProducts(search = '') {
        const url = search
            ? `/api/products?search=${encodeURIComponent(search)}`
            : '/api/products';
        const res = await fetch(url);
        return await res.json();
    },
    async getProductDetail(hs6) {
        const res = await fetch(`/api/products/${hs6}`);
        return await res.json();
    },
    async getNaics() {
        const res = await fetch('/api/naics');
        return await res.json();
    },
    async getNaicsProducts(code) {
        const res = await fetch(`/api/naics/${code}`);
        return await res.json();
    },
    async getCritical(minDeficit, minDefense) {
        const url = `/api/critical?min_china_deficit=${minDeficit}&min_defense_score=${minDefense}`;
        const res = await fetch(url);
        return await res.json();
    },
};

// Tab management
function switchTab(tabName) {
    state.currentTab = tabName;

    // Update tab buttons
    document.querySelectorAll('.tab').forEach((tab) => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach((content) => {
        content.classList.toggle('active', content.id === `tab-${tabName}`);
    });

    // Load data if needed
    if (tabName === 'products' && state.products.length === 0) {
        loadProducts();
    } else if (tabName === 'naics' && state.naics.length === 0) {
        loadNaics();
    } else if (tabName === 'critical') {
        loadCritical();
    }
}

// Stats loading
async function loadStats() {
    const stats = await api.getStats();
    document.getElementById('stats').innerHTML = `
        <span><strong>${fmt.number(stats.total_hs6)}</strong> HS6 codes</span>
        <span><strong>${fmt.number(stats.total_naics)}</strong> NAICS</span>
        <span><strong>$${fmt.number(stats.total_china_deficit)}</strong> China deficit</span>
        <span><strong>${stats.high_defense_count}</strong> high-defense</span>
    `;
}

// Products tab
async function loadProducts(search = '') {
    const tbody = document.querySelector('#products-table tbody');
    tbody.innerHTML = '<tr><td colspan="8" class="loading">Loading...</td></tr>';

    const data = await api.getProducts(search);
    state.products = data.products;

    document.getElementById('product-count').textContent = `${data.total} products`;

    if (state.products.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty">No products found</td></tr>';
        return;
    }

    renderProductsTable();
}

function renderProductsTable() {
    const tbody = document.querySelector('#products-table tbody');
    tbody.innerHTML = state.products
        .map(
            (p) => `
        <tr onclick="showProductDetail('${p.hs6}')">
            <td><code>${p.hs6}</code></td>
            <td>${p.description}</td>
            <td class="number">${fmt.full(p.china_deficit)}</td>
            <td class="number">${fmt.percent(p.china_import_share)}</td>
            <td class="number ${p.defense_score >= 7 ? 'high-score' : ''}">${p.defense_score}</td>
            <td class="number ${p.trade_balance < 0 ? 'negative' : 'positive'}">${fmt.full(p.trade_balance)}</td>
            <td class="number">${fmt.full(p.total_exports)}</td>
            <td class="number">${fmt.full(p.total_imports)}</td>
        </tr>
    `
        )
        .join('');
}

// NAICS tab
async function loadNaics() {
    const tbody = document.querySelector('#naics-table tbody');
    tbody.innerHTML = '<tr><td colspan="5" class="loading">Loading...</td></tr>';

    const data = await api.getNaics();
    state.naics = data.naics;

    document.getElementById('naics-count').textContent = `${state.naics.length} industries`;

    renderNaicsTable();
}

function renderNaicsTable() {
    const tbody = document.querySelector('#naics-table tbody');
    tbody.innerHTML = state.naics
        .map(
            (n) => `
        <tr onclick="showNaicsDetail('${n.code}')">
            <td><code>${n.code}</code></td>
            <td>${n.name}</td>
            <td class="number">${n.product_count}</td>
            <td class="number">${fmt.full(n.total_china_deficit)}</td>
            <td class="number ${n.avg_defense_score >= 7 ? 'high-score' : ''}">${n.avg_defense_score}</td>
        </tr>
    `
        )
        .join('');
}

// Critical matrix tab
async function loadCritical() {
    const minDeficit = parseInt(document.getElementById('critical-min-deficit').value) || 0;
    const minDefense = parseInt(document.getElementById('critical-min-defense').value) || 0;

    const tbody = document.querySelector('#critical-table tbody');
    tbody.innerHTML = '<tr><td colspan="5" class="loading">Loading...</td></tr>';

    const data = await api.getCritical(minDeficit, minDefense);
    state.critical = data.products;

    document.getElementById('critical-count').textContent = `${data.total} critical products`;

    if (state.critical.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">No products match criteria</td></tr>';
        return;
    }

    renderCriticalTable();
}

function renderCriticalTable() {
    const tbody = document.querySelector('#critical-table tbody');
    tbody.innerHTML = state.critical
        .map(
            (p) => `
        <tr onclick="showProductDetail('${p.hs6}')">
            <td><code>${p.hs6}</code></td>
            <td>${p.description}</td>
            <td class="number">${fmt.full(p.china_deficit)}</td>
            <td class="number high-score">${p.defense_score}</td>
            <td class="number">${(p.criticality * 100).toFixed(1)}%</td>
        </tr>
    `
        )
        .join('');
}

// Product detail view
async function showProductDetail(hs6) {
    const detail = await api.getProductDetail(hs6);

    document.getElementById('detail-title').textContent = detail.description;
    document.getElementById('detail-hs6').textContent = detail.hs6;
    document.getElementById('detail-description').textContent = detail.description;
    document.getElementById('detail-china-deficit').textContent = '$' + fmt.full(detail.china_deficit);
    document.getElementById('detail-china-import-share').textContent = fmt.percent(detail.china_import_share);
    document.getElementById('detail-defense-score').textContent = detail.defense_score;
    document.getElementById('detail-defense-reasoning').textContent = detail.defense_reasoning;

    // Render NAICS
    const naicsHtml =
        detail.naics.length > 0
            ? detail.naics
                  .map(
                      (n) => `
            <div class="naics-badge">
                <span class="code">${n.code}</span>
                <span class="name">${n.name}</span>
            </div>
        `
                  )
                  .join('')
            : '<p class="empty">No NAICS mappings found</p>';
    document.getElementById('detail-naics').innerHTML = naicsHtml;

    // Render countries table
    const countriesTbody = document.querySelector('#detail-countries-table tbody');
    countriesTbody.innerHTML = detail.countries
        .map(
            (c) => `
        <tr>
            <td>${c.country}</td>
            <td class="number">${fmt.full(c.exports)}</td>
            <td class="number">${fmt.full(c.imports)}</td>
            <td class="number ${c.balance < 0 ? 'negative' : 'positive'}">${fmt.full(c.balance)}</td>
        </tr>
    `
        )
        .join('');

    // Show detail tab
    document.getElementById('detail-tab').style.display = 'block';
    switchTab('detail');
}

// NAICS detail view (shows products in that NAICS)
async function showNaicsDetail(code) {
    const data = await api.getNaicsProducts(code);

    // Temporarily use products table to show NAICS products
    state.products = data.products;
    document.getElementById('product-count').textContent = `${data.products.length} products in ${data.name}`;

    // Switch to products tab
    switchTab('products');
    renderProductsTable();
}

// Table sorting
function sortTable(tableName, field) {
    const dataKey = {
        products: 'products',
        naics: 'naics',
        critical: 'critical',
    }[tableName];

    const data = state[dataKey];

    // Toggle sort order
    if (state.currentSort.field === field) {
        state.currentSort.order = state.currentSort.order === 'asc' ? 'desc' : 'asc';
    } else {
        state.currentSort.field = field;
        state.currentSort.order = 'desc';
    }

    // Sort data
    data.sort((a, b) => {
        const aVal = a[field];
        const bVal = b[field];
        const order = state.currentSort.order === 'asc' ? 1 : -1;

        if (typeof aVal === 'number') {
            return (aVal - bVal) * order;
        }
        return String(aVal).localeCompare(String(bVal)) * order;
    });

    // Update UI
    const table = document.getElementById(`${tableName}-table`);
    table.querySelectorAll('th[data-sort]').forEach((th) => {
        th.classList.remove('asc', 'desc');
        if (th.dataset.sort === field) {
            th.classList.add(state.currentSort.order);
        }
    });

    // Re-render table
    if (tableName === 'products') renderProductsTable();
    else if (tableName === 'naics') renderNaicsTable();
    else if (tableName === 'critical') renderCriticalTable();
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing...');

    // Load initial data with error handling
    loadStats().catch(err => {
        console.error('Error loading stats:', err);
        document.getElementById('stats').innerHTML = '<span style="color: #ef4444;">Error loading stats</span>';
    });

    loadProducts().catch(err => {
        console.error('Error loading products:', err);
        const tbody = document.querySelector('#products-table tbody');
        tbody.innerHTML = '<tr><td colspan="8" class="empty" style="color: #ef4444;">Error loading products</td></tr>';
    });

    // Tab switching
    document.querySelectorAll('.tab').forEach((tab) => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            if (tabName !== 'detail') {
                document.getElementById('detail-tab').style.display = 'none';
            }
            switchTab(tabName);
        });
    });

    // Product search
    let searchTimeout;
    document.getElementById('product-search').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            loadProducts(e.target.value);
        }, 300);
    });

    // Product search clear
    document.getElementById('product-clear').addEventListener('click', () => {
        document.getElementById('product-search').value = '';
        loadProducts('');
    });

    // Critical filters
    document.getElementById('critical-apply').addEventListener('click', () => {
        loadCritical();
    });

    // Critical filters reset
    document.getElementById('critical-reset').addEventListener('click', () => {
        document.getElementById('critical-min-deficit').value = '100000000';
        document.getElementById('critical-min-defense').value = '7';
        loadCritical();
    });

    // Back button
    document.getElementById('back-btn').addEventListener('click', () => {
        document.getElementById('detail-tab').style.display = 'none';
        switchTab('products');
    });

    // Table sorting
    document.querySelectorAll('#products-table th[data-sort]').forEach((th) => {
        th.addEventListener('click', () => sortTable('products', th.dataset.sort));
    });

    document.querySelectorAll('#naics-table th[data-sort]').forEach((th) => {
        th.addEventListener('click', () => sortTable('naics', th.dataset.sort));
    });

    document.querySelectorAll('#critical-table th[data-sort]').forEach((th) => {
        th.addEventListener('click', () => sortTable('critical', th.dataset.sort));
    });
});

// Expose functions globally for inline event handlers
window.showProductDetail = showProductDetail;
window.showNaicsDetail = showNaicsDetail;
