// 配置
const API_BASE_URL = 'http://localhost:8000/api';
let token = localStorage.getItem('token');
let currentUser = null;
let mainMap = null;
let lineMapInstance = null;
let heatmapInstance = null;
let heatmapAutoRefresh = false;
let heatmapRefreshTimer = null;

// 工具函数：显示通知
function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification show ${type}`;
    setTimeout(() => {
        notification.classList.remove('show');
    }, 3000);
}

// 工具函数：API 请求
async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...options.headers
    };

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            ...options,
            headers,
            mode: 'cors',
            credentials: 'omit'
        });

        if (!response.ok) {
            let errorMessage = '请求失败';
            try {
                const data = await response.json();
                errorMessage = data.detail?.message || data.detail || data.message || errorMessage;
                const error = new Error(errorMessage);
                error.code = data.detail?.code;
                throw error;
            } catch (e) {
                if (e instanceof Error && e.code) throw e;
                errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }

        // 处理204 No Content响应
        if (response.status === 204) {
            return null;
        }

        const data = await response.json();
        return data;
    } catch (error) {
        showNotification(
            error.message,
            error.code === 'PASSWORD_INVALID' ? 'warning' : 'error'
        );
        throw error;
    }
}

// 初始化地图
function initMap(containerId, center = [121.4751080, 31.2326870]) {
    const map = new maplibregl.Map({
        container: containerId,
        style: {
            version: 8,
            sources: {
                'osm': {
                    type: 'raster',
                    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                    tileSize: 256,
                    attribution: '© OpenStreetMap contributors'
                }
            },
            layers: [{
                id: 'osm',
                type: 'raster',
                source: 'osm'
            }]
        },
        center: center,
        zoom: 12
    });

    map.addControl(new maplibregl.NavigationControl());
    return map;
}

// GCJ-02 转 WGS84 (简化版，实际应使用精确算法)
function gcj02ToWgs84(lng, lat) {
    const PI = 3.14159265358979324;
    const a = 6378245.0;
    const ee = 0.00669342162296594323;

    function transformLat(lng, lat) {
        let ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * Math.sqrt(Math.abs(lng));
        ret += (20.0 * Math.sin(6.0 * lng * PI) + 20.0 * Math.sin(2.0 * lng * PI)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(lat * PI) + 40.0 * Math.sin(lat / 3.0 * PI)) * 2.0 / 3.0;
        ret += (160.0 * Math.sin(lat / 12.0 * PI) + 320 * Math.sin(lat * PI / 30.0)) * 2.0 / 3.0;
        return ret;
    }

    function transformLng(lng, lat) {
        let ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * Math.sqrt(Math.abs(lng));
        ret += (20.0 * Math.sin(6.0 * lng * PI) + 20.0 * Math.sin(2.0 * lng * PI)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(lng * PI) + 40.0 * Math.sin(lng / 3.0 * PI)) * 2.0 / 3.0;
        ret += (150.0 * Math.sin(lng / 12.0 * PI) + 300.0 * Math.sin(lng / 30.0 * PI)) * 2.0 / 3.0;
        return ret;
    }

    let dLat = transformLat(lng - 105.0, lat - 35.0);
    let dLng = transformLng(lng - 105.0, lat - 35.0);
    let radLat = lat / 180.0 * PI;
    let magic = Math.sin(radLat);
    magic = 1 - ee * magic * magic;
    let sqrtMagic = Math.sqrt(magic);
    dLat = (dLat * 180.0) / ((a * (1 - ee)) / (magic * sqrtMagic) * PI);
    dLng = (dLng * 180.0) / (a / sqrtMagic * Math.cos(radLat) * PI);

    return [lng - dLng, lat - dLat];
}

// 认证相关
document.getElementById('authForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('authUsername').value;
    const password = document.getElementById('authPassword').value;
    const isLogin = document.getElementById('authTitle').textContent === '登录';

    try {
        if (isLogin) {
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);

            const response = await fetch(`${API_BASE_URL}/auth/login`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || '登录失败');
            }

            token = data.access_token;
            localStorage.setItem('token', token);
            showNotification('登录成功', 'success');
            await loadCurrentUser();
        } else {
            await apiRequest('/auth/register', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            showNotification('注册成功，请登录', 'success');
            toggleAuthMode();
        }
    } catch (error) {
        const isPasswordError = !isLogin && error.code === 'PASSWORD_INVALID';
        showNotification(error.message, isPasswordError ? 'warning' : 'error');
    }
});

document.getElementById('authToggleLink')?.addEventListener('click', (e) => {
    e.preventDefault();
    toggleAuthMode();
});

function toggleAuthMode() {
    const title = document.getElementById('authTitle');
    const toggleText = document.getElementById('authToggleText');
    const toggleLink = document.getElementById('authToggleLink');
    const submitBtn = document.querySelector('#authForm button');

    if (title.textContent === '登录') {
        title.textContent = '注册';
        submitBtn.textContent = '注册';
        toggleText.textContent = '已有账号？';
        toggleLink.textContent = '立即登录';
    } else {
        title.textContent = '登录';
        submitBtn.textContent = '登录';
        toggleText.textContent = '没有账号？';
        toggleLink.textContent = '立即注册';
    }
}

document.getElementById('logoutBtn')?.addEventListener('click', () => {
    token = null;
    currentUser = null;
    localStorage.removeItem('token');
    document.getElementById('authPage').style.display = 'block';
    document.getElementById('appPage').style.display = 'none';
    showNotification('已退出登录', 'info');
});

async function loadCurrentUser() {
    try {
        currentUser = await apiRequest('/auth/me');
        document.getElementById('username').textContent = `${currentUser.username} (${getRoleName(currentUser.role)})`;
        document.getElementById('logoutBtn').style.display = 'block';
        document.getElementById('authPage').style.display = 'none';
        document.getElementById('appPage').style.display = 'flex';

        // 设置角色权限
        document.body.className = currentUser.role;

        // 初始化主地图
        if (!mainMap) {
            setTimeout(() => {
                mainMap = initMap('map');
            }, 100);
        }
    } catch (error) {
        console.error('Failed to load user:', error);
    }
}

function getRoleName(role) {
    const names = {
        passenger: '普通用户',
        analyst: '分析师',
        admin: '管理员'
    };
    return names[role] || role;
}

// 导航切换
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const page = item.dataset.page;

        // 更新导航状态
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');

        // 切换页面
        document.querySelectorAll('.content-page').forEach(p => p.classList.remove('active'));
        document.getElementById(`${page}Page`).classList.add('active');

        // 加载页面数据
        loadPageData(page);
    });
});

function loadPageData(page) {
    switch (page) {
        case 'favorites':
            loadFavorites();
            break;
        case 'heatmap':
            if (!heatmapInstance) {
                setTimeout(() => {
                    heatmapInstance = initMap('heatmap');
                    heatmapInstance.resize();
                    heatmapInstance.on('moveend', () => {
                        if (!heatmapAutoRefresh) return;
                        clearTimeout(heatmapRefreshTimer);
                        heatmapRefreshTimer = setTimeout(() => loadHeatmapData(false), 250);
                    });
                }, 100);
            } else {
                setTimeout(() => heatmapInstance.resize(), 0);
            }
            break;
        case 'analytics':
            initializeAnalyticsTimeRange();
            break;
        case 'admin':
            loadUsers();
            break;
        case 'ingestion':
            loadIngestionRuns();
            break;
    }
}

function formatLocalDateTime(date) {
    const pad = value => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
        + `T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function initializeAnalyticsTimeRange() {
    const now = new Date();
    const start = new Date(now);
    const originalDay = start.getDate();

    // Move to the target month first, then clamp dates such as March 31 to February 28/29.
    start.setDate(1);
    start.setMonth(start.getMonth() - 1);
    const lastDayOfTargetMonth = new Date(
        start.getFullYear(),
        start.getMonth() + 1,
        0
    ).getDate();
    start.setDate(Math.min(originalDay, lastDayOfTargetMonth));
    start.setHours(0, 0, 0, 0);

    const startValue = formatLocalDateTime(start);
    const endValue = formatLocalDateTime(now);
    const inputPairs = [
        ['popStartTime', 'popEndTime'],
        ['linePopStartTime', 'linePopEndTime'],
        ['distStartTime', 'distEndTime']
    ];

    inputPairs.forEach(([startId, endId]) => {
        const startInput = document.getElementById(startId);
        const endInput = document.getElementById(endId);
        if (startInput && !startInput.value) startInput.value = startValue;
        if (endInput && !endInput.value) endInput.value = endValue;
    });
}

// 标签页切换
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;
        const parent = btn.closest('.content-page');

        parent.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        parent.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        parent.querySelector(`#${tabName}`).classList.add('active');
    });
});

// 站点搜索
document.getElementById('searchType')?.addEventListener('change', (e) => {
    const searchInput = document.getElementById('searchInput');
    if (e.target.value === 'stop') {
        searchInput.placeholder = '输入站点名称';
    } else {
        searchInput.placeholder = '输入线路名称（如：123路）';
    }
});

document.getElementById('searchBtn')?.addEventListener('click', async () => {
    const searchType = document.getElementById('searchType').value;
    const query = document.getElementById('searchInput').value;
    const cityCode = document.getElementById('cityCode').value;
    const refresh = document.getElementById('refreshFromAmap')?.checked || false;

    if (!query.trim()) {
        showNotification('请输入搜索内容', 'error');
        return;
    }

    try {
        if (searchType === 'stop') {
            const params = new URLSearchParams({ q: query, limit: 20 });
            if (cityCode) params.append('city_code', cityCode);
            if (refresh) params.append('refresh', 'true');
            const data = await apiRequest(`/stops/search?${params}`);
            await displaySearchResults(data, 'stop');
        } else {
            const params = new URLSearchParams({ q: query, limit: 20 });
            if (cityCode) params.append('city_code', cityCode);
            if (refresh) params.append('refresh', 'true');
            const data = await apiRequest(`/lines/search?${params}`);
            await displaySearchResults(data, 'line');
        }
    } catch (error) {
        document.getElementById('searchResults').innerHTML = '<div class="empty-state">搜索失败</div>';
    }
});

async function displaySearchResults(data, type) {
    const container = document.getElementById('searchResults');

    if (type === 'stop') {
        const stops = data.items || data.stops || data.data || [];

        if (stops.length === 0) {
            container.innerHTML = '<div class="empty-state">未找到结果</div>';
            return;
        }

        // 获取用户收藏列表以标记已收藏的站点
        let favoriteStopIds = new Set();
        try {
            const favData = await apiRequest('/me/favorite-stops?limit=100');
            favoriteStopIds = new Set((favData.items || []).map(item => (item.stop || item).id));
        } catch (e) {
            console.log('未登录或无法获取收藏');
        }

        container.innerHTML = stops.map(stop => {
            const isFavorite = favoriteStopIds.has(stop.id);
            return `
                <div class="stop-item" onclick="showStopDetail(${stop.id})">
                    <button class="favorite-btn ${isFavorite ? 'active' : ''}"
                            onclick="event.stopPropagation(); toggleFavoriteStop(${stop.id}, this)">
                        ${isFavorite ? '★' : '☆'}
                    </button>
                    <h4>${stop.stop_name}</h4>
                    <p>坐标: ${stop.longitude}, ${stop.latitude}</p>
                    <p>数据来源: ${data.data_source || 'database'}</p>
                </div>
            `;
        }).join('');

        // 在地图上显示站点
        if (mainMap && stops.length > 0) {
            const features = stops.map(stop => {
                const [lng, lat] = gcj02ToWgs84(parseFloat(stop.longitude), parseFloat(stop.latitude));
                return {
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [lng, lat]
                    },
                    properties: {
                        id: stop.id,
                        name: stop.stop_name
                    }
                };
            });

            if (mainMap.getSource('stops')) {
                mainMap.getSource('stops').setData({
                    type: 'FeatureCollection',
                    features: features
                });
            } else {
                mainMap.addSource('stops', {
                    type: 'geojson',
                    data: {
                        type: 'FeatureCollection',
                        features: features
                    }
                });

                mainMap.addLayer({
                    id: 'stops',
                    type: 'circle',
                    source: 'stops',
                    paint: {
                        'circle-radius': 8,
                        'circle-color': '#1976d2',
                        'circle-stroke-width': 2,
                        'circle-stroke-color': '#fff'
                    }
                });

                mainMap.on('click', 'stops', (e) => {
                    const stopId = e.features[0].properties.id;
                    showStopDetail(stopId, 'line_map');
                });
            }

            // 调整地图视角
            const bounds = new maplibregl.LngLatBounds();
            features.forEach(f => bounds.extend(f.geometry.coordinates));
            mainMap.fitBounds(bounds, { padding: 50 });
        }
    } else {
        // 线路搜索结果
        const lines = data.items || data.lines || data.data || [];

        if (lines.length === 0) {
            container.innerHTML = '<div class="empty-state">未找到结果</div>';
            return;
        }

        // 获取用户收藏的线路列表
        let favoriteLineIds = new Set();
        try {
            const favData = await apiRequest('/me/favorite-lines?limit=100');
            favoriteLineIds = new Set((favData.items || []).map(item => (item.line || item).id));
        } catch (e) {
            console.log('未登录或无法获取收藏');
        }

        container.innerHTML = lines.map(line => {
            const isFavorite = favoriteLineIds.has(line.id);
            return `
                <div class="line-item" onclick="showLineDetail(${line.id})">
                    <button class="favorite-btn ${isFavorite ? 'active' : ''}"
                            onclick="event.stopPropagation(); toggleFavoriteLine(${line.id}, this)">
                        ${isFavorite ? '★' : '☆'}
                    </button>
                    <h4>${line.line_name || line.amap_name}</h4>
                    <p>${line.start_stop_name || ''} → ${line.end_stop_name || ''}</p>
                    ${line.first_departure_time ? `<p>首班: ${line.first_departure_time} | 末班: ${line.last_departure_time || 'N/A'}</p>` : ''}
                </div>
            `;
        }).join('');

        // 清除地图上的站点标记
        if (mainMap && mainMap.getSource('stops')) {
            mainMap.getSource('stops').setData({
                type: 'FeatureCollection',
                features: []
            });
        }
    }
}

// 站点详情
async function showStopDetail(stopId, entryPoint = 'search') {
    console.log('showStopDetail called with:', stopId, entryPoint);
    try {
        const params = new URLSearchParams({ entry_point: entryPoint });
        console.log('Fetching stop data...');
        const data = await apiRequest(`/stops/${stopId}?${params}`);
        console.log('Stop data received:', data);
        const stop = data.stop || data;

        // 检查是否已收藏
        let isFavorite = false;
        try {
            const favData = await apiRequest('/me/favorite-stops?limit=100');
            const favoriteStopIds = new Set((favData.items || []).map(item => (item.stop || item).id));
            isFavorite = favoriteStopIds.has(stop.id);
        } catch (e) {
            console.log('未登录或无法获取收藏');
        }

        document.getElementById('stopName').innerHTML = `
            ${stop.stop_name}
            <button class="favorite-btn-large ${isFavorite ? 'active' : ''}"
                    onclick="toggleFavoriteStop(${stop.id}, this)">
                ${isFavorite ? '★' : '☆'} ${isFavorite ? '已收藏' : '收藏'}
            </button>
        `;

        document.getElementById('stopDetails').innerHTML = `
            <div class="detail-item"><label>站点ID:</label> ${stop.id}</div>
            <div class="detail-item"><label>高德ID:</label> ${stop.amap_stop_id || 'N/A'}</div>
            <div class="detail-item"><label>坐标:</label> ${stop.longitude}, ${stop.latitude}</div>
            <div class="detail-item"><label>城市编码:</label> ${stop.city_code || 'N/A'}</div>
            <div class="detail-item"><label>坐标系:</label> ${stop.coordinate_system}</div>
            <div class="detail-item"><label>数据来源:</label> ${data.data_source || 'database'}</div>
            ${stop.updated_at ? `<div class="detail-item"><label>更新时间:</label> ${new Date(stop.updated_at).toLocaleString('zh-CN')}</div>` : ''}
        `;

        // 加载途经线路
        console.log('Fetching lines data...');
        const linesData = await apiRequest(`/stops/${stopId}/lines`);
        console.log('Lines data received:', linesData);
        const lines = linesData.lines || [];
        const unresolvedSummaries = linesData.unresolved_summaries || [];

        // 获取收藏的线路列表
        let favoriteLineIds = new Set();
        try {
            const favData = await apiRequest('/me/favorite-lines?limit=100');
            favoriteLineIds = new Set((favData.items || []).map(item => (item.line || item).id));
        } catch (e) {
            console.log('未登录或无法获取收藏');
        }

        let linesHtml = '';

        // 显示已解析的完整线路
        if (lines.length > 0) {
            linesHtml += lines.map(line => {
                const isFav = favoriteLineIds.has(line.id);
                return `
                    <div class="line-item" onclick="showLineDetail(${line.id})">
                        <button class="favorite-btn ${isFav ? 'active' : ''}"
                                onclick="event.stopPropagation(); toggleFavoriteLine(${line.id}, this)">
                            ${isFav ? '★' : '☆'}
                        </button>
                        <h4>${line.line_name || line.amap_name}</h4>
                        <p>${line.start_stop_name || ''} → ${line.end_stop_name || ''}</p>
                        ${line.first_departure_time ? `<p>首班: ${line.first_departure_time} | 末班: ${line.last_departure_time || 'N/A'}</p>` : ''}
                    </div>
                `;
            }).join('');
        }

        // 显示未解析的线路摘要（可点击补全）
        if (unresolvedSummaries.length > 0) {
            linesHtml += unresolvedSummaries.map(summary => `
                <div class="line-item unresolved" onclick="resolveLineSummary('${summary.amap_line_id}')">
                    <h4>${summary.line_name || summary.amap_name} <span style="color: #999; font-size: 12px;">[点击加载详情]</span></h4>
                    <p>${summary.start_stop_name || ''} → ${summary.end_stop_name || ''}</p>
                </div>
            `).join('');
        }

        if (linesHtml === '') {
            document.getElementById('stopLines').innerHTML = '<div class="empty-state">暂无途经线路</div>';
        } else {
            document.getElementById('stopLines').innerHTML = linesHtml;
        }

        console.log('Opening modal...');
        document.getElementById('stopModal').classList.add('show');
        console.log('Modal opened successfully');

        // 渲染站点地图
        const [lng, lat] = gcj02ToWgs84(parseFloat(stop.longitude), parseFloat(stop.latitude));

        setTimeout(() => {
            console.log('Initializing stop map...');

            if (!window.stopMapInstance) {
                window.stopMapInstance = initMap('stopMap', [lng, lat]);

                window.stopMapInstance.on('load', () => {
                    renderStopMarker(lng, lat);
                });
            } else {
                if (window.stopMapInstance.isStyleLoaded()) {
                    renderStopMarker(lng, lat);
                } else {
                    window.stopMapInstance.once('styledata', () => {
                        renderStopMarker(lng, lat);
                    });
                }
            }
        }, 200);
    } catch (error) {
        console.error('Error in showStopDetail:', error);
        showNotification('加载站点详情失败: ' + error.message, 'error');
    }
}

// 渲染站点标记
function renderStopMarker(lng, lat) {
    if (!window.stopMapInstance) return;

    console.log('Rendering stop marker at:', lng, lat);

    // 清理旧图层
    if (window.stopMapInstance.getLayer('stop-marker')) {
        window.stopMapInstance.removeLayer('stop-marker');
    }
    if (window.stopMapInstance.getSource('stop-marker')) {
        window.stopMapInstance.removeSource('stop-marker');
    }

    // 添加站点标记
    window.stopMapInstance.addSource('stop-marker', {
        type: 'geojson',
        data: {
            type: 'Feature',
            geometry: {
                type: 'Point',
                coordinates: [lng, lat]
            }
        }
    });

    window.stopMapInstance.addLayer({
        id: 'stop-marker',
        type: 'circle',
        source: 'stop-marker',
        paint: {
            'circle-radius': 10,
            'circle-color': '#ff5722',
            'circle-stroke-width': 3,
            'circle-stroke-color': '#fff'
        }
    });

    // 跳转到站点位置
    window.stopMapInstance.flyTo({
        center: [lng, lat],
        zoom: 16,
        essential: true
    });

    console.log('Stop marker rendered successfully');
}

// 解析未解析的线路摘要
async function resolveLineSummary(amapLineId) {
    try {
        showNotification('正在从高德获取线路详情...', 'info');
        const data = await apiRequest(`/lines/by-amap/${amapLineId}`);
        const line = data.line || data;

        showNotification('线路详情已加载', 'success');
        // 直接显示线路详情
        await showLineDetail(line.id);
    } catch (error) {
        showNotification('获取线路详情失败: ' + error.message, 'error');
    }
}

// 线路详情
async function showLineDetail(lineId) {
    try {
        const data = await apiRequest(`/lines/${lineId}`);
        const line = data.line || data;

        // 检查是否已收藏
        let isFavorite = false;
        try {
            const favData = await apiRequest('/me/favorite-lines?limit=100');
            const favoriteLineIds = new Set((favData.items || []).map(item => (item.line || item).id));
            isFavorite = favoriteLineIds.has(line.id);
        } catch (e) {
            console.log('未登录或无法获取收藏');
        }

        document.getElementById('lineName').innerHTML = `
            ${line.amap_name || line.line_name}
            <button class="favorite-btn-large ${isFavorite ? 'active' : ''}"
                    onclick="toggleFavoriteLine(${line.id}, this)">
                ${isFavorite ? '★' : '☆'} ${isFavorite ? '已收藏' : '收藏'}
            </button>
        `;

        document.getElementById('lineDetails').innerHTML = `
            <div class="detail-item"><label>线路ID:</label> ${line.id}</div>
            <div class="detail-item"><label>高德ID:</label> ${line.amap_line_id}</div>
            <div class="detail-item"><label>线路名称:</label> ${line.line_name}</div>
            <div class="detail-item"><label>起点:</label> ${line.start_stop_name || 'N/A'}</div>
            <div class="detail-item"><label>终点:</label> ${line.end_stop_name || 'N/A'}</div>
            <div class="detail-item"><label>首班:</label> ${line.first_departure_time || 'N/A'}</div>
            <div class="detail-item"><label>末班:</label> ${line.last_departure_time || 'N/A'}</div>
            <div class="detail-item"><label>线路类型:</label> ${line.amap_type || 'N/A'}</div>
            <div class="detail-item"><label>运营公司:</label> ${line.company_name || 'N/A'}</div>
            <div class="detail-item"><label>全程距离:</label> ${line.distance_km ? line.distance_km + ' km' : 'N/A'}</div>
            <div class="detail-item"><label>票价:</label> ${line.basic_price ? '¥' + line.basic_price : 'N/A'}</div>
            <div class="detail-item"><label>数据来源:</label> ${data.data_source || 'database'}</div>
        `;

        // 加载站点列表
        const stopsData = await apiRequest(`/lines/${lineId}/stops`);
        const stopsArray = stopsData.stops || [];

        // 获取收藏的站点列表
        let favoriteStopIds = new Set();
        try {
            const favData = await apiRequest('/me/favorite-stops?limit=100');
            favoriteStopIds = new Set((favData.items || []).map(item => (item.stop || item).id));
        } catch (e) {
            console.log('未登录或无法获取收藏');
        }

        if (stopsArray.length === 0) {
            document.getElementById('lineStops').innerHTML = '<div class="empty-state">暂无站点信息</div>';
        } else {
            document.getElementById('lineStops').innerHTML = stopsArray.map((item) => {
                const stop = item.stop || item;
                const seq = item.sequence_no || 0;
                const isFav = favoriteStopIds.has(stop.id);
                return `
                    <div class="stop-item" id="line-stop-${stop.id}" onclick="showStopInLineMap(${stop.id}, ${lineId})">
                        <button class="favorite-btn ${isFav ? 'active' : ''}"
                                onclick="event.stopPropagation(); toggleFavoriteStop(${stop.id}, this)">
                            ${isFav ? '★' : '☆'}
                        </button>
                        <h4>${seq}. ${stop.stop_name}</h4>
                        <p>${stop.longitude}, ${stop.latitude}</p>
                    </div>
                `;
            }).join('');
        }

        // 加载线路地图
        try {
            const mapData = await apiRequest(`/lines/${lineId}/map`);
            const geojson = mapData.geojson || mapData;

            if (!lineMapInstance) {
                setTimeout(() => {
                    lineMapInstance = initMap('lineMap');
                    // 等待地图加载完成后再渲染
                    lineMapInstance.on('load', () => {
                        renderLineMap(geojson, stopsArray, line.ui_color);
                    });
                }, 100);
            } else {
                // 如果地图已存在，检查是否已加载完成
                if (lineMapInstance.isStyleLoaded()) {
                    renderLineMap(geojson, stopsArray, line.ui_color);
                } else {
                    lineMapInstance.once('styledata', () => {
                        renderLineMap(geojson, stopsArray, line.ui_color);
                    });
                }
            }
        } catch (error) {
            console.error('地图加载失败:', error);
            document.getElementById('lineMap').innerHTML = '<div class="empty-state">地图加载失败</div>';
        }

        document.getElementById('lineModal').classList.add('show');
    } catch (error) {
        showNotification('加载线路详情失败: ' + error.message, 'error');
    }
}

// 在线路地图中显示站点详情
async function showStopInLineMap(stopId, lineId) {
    // 如果点击的是已选中的站点，则回收
    const selectedStop = document.getElementById(`line-stop-${stopId}`);
    if (selectedStop && selectedStop.classList.contains('selected')) {
        closeStopExpanded(stopId);
        return;
    }

    try {
        // 高亮选中的站点
        document.querySelectorAll('#lineStops .stop-item').forEach(el => el.classList.remove('selected'));
        if (selectedStop) {
            selectedStop.classList.add('selected');
        }

        // 获取站点数据
        const stopsData = await apiRequest(`/lines/${lineId}/stops`);
        const stopsArray = stopsData.stops || [];
        const stopItem = stopsArray.find(item => (item.stop || item).id === stopId);
        const stop = stopItem ? (stopItem.stop || stopItem) : null;

        if (!stop) {
            showNotification('未找到站点信息', 'error');
            return;
        }

        // 地图跳转到站点位置
        if (lineMapInstance) {
            const [lng, lat] = gcj02ToWgs84(parseFloat(stop.longitude), parseFloat(stop.latitude));
            lineMapInstance.flyTo({
                center: [lng, lat],
                zoom: 15,
                essential: true
            });

            // 添加高亮标记
            if (lineMapInstance.getLayer('selected-stop')) {
                lineMapInstance.removeLayer('selected-stop');
                lineMapInstance.removeSource('selected-stop');
            }

            lineMapInstance.addSource('selected-stop', {
                type: 'geojson',
                data: {
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [lng, lat]
                    }
                }
            });

            lineMapInstance.addLayer({
                id: 'selected-stop',
                type: 'circle',
                source: 'selected-stop',
                paint: {
                    'circle-radius': 12,
                    'circle-color': '#ff5722',
                    'circle-stroke-width': 3,
                    'circle-stroke-color': '#fff'
                }
            });
        }

        // 加载站点详情和途经线路
        const params = new URLSearchParams({ entry_point: 'line_map' });
        const stopData = await apiRequest(`/stops/${stopId}?${params}`);
        const linesData = await apiRequest(`/stops/${stopId}/lines`);

        // 获取收藏状态
        let isFavoriteStop = false;
        let favoriteLineIds = new Set();
        try {
            const favStopsData = await apiRequest('/me/favorite-stops?limit=100');
            const favoriteStopIds = new Set((favStopsData.items || []).map(item => (item.stop || item).id));
            isFavoriteStop = favoriteStopIds.has(stopId);

            const favLinesData = await apiRequest('/me/favorite-lines?limit=100');
            favoriteLineIds = new Set((favLinesData.items || []).map(item => (item.line || item).id));
        } catch (e) {
            console.log('未登录或无法获取收藏');
        }

        const lines = linesData.lines || [];
        const unresolvedSummaries = linesData.unresolved_summaries || [];

        // 在站点列表下方显示展开的详情
        const expandedHtml = `
            <div class="stop-expanded" id="stop-expanded-${stopId}">
                <div class="stop-expanded-header">
                    <h4>
                        ${stop.stop_name}
                        <button class="favorite-btn-small ${isFavoriteStop ? 'active' : ''}"
                                onclick="event.stopPropagation(); toggleFavoriteStop(${stopId}, this)">
                            ${isFavoriteStop ? '★' : '☆'}
                        </button>
                    </h4>
                    <button class="close-btn" onclick="closeStopExpanded(${stopId})">×</button>
                </div>
                <div class="stop-expanded-content">
                    <p><strong>坐标:</strong> ${stop.longitude}, ${stop.latitude}</p>
                    <p><strong>城市编码:</strong> ${stop.city_code || 'N/A'}</p>
                    <h5>途经线路:</h5>
                    ${lines.length === 0 && unresolvedSummaries.length === 0 ? '<p>暂无途经线路</p>' : ''}
                    ${lines.map(line => {
                        const isFav = favoriteLineIds.has(line.id);
                        return `
                            <div class="mini-line-item">
                                <button class="favorite-btn-small ${isFav ? 'active' : ''}"
                                        onclick="event.stopPropagation(); toggleFavoriteLine(${line.id}, this)">
                                    ${isFav ? '★' : '☆'}
                                </button>
                                <span>${line.line_name || line.amap_name}</span>
                            </div>
                        `;
                    }).join('')}
                    ${unresolvedSummaries.map(summary => `
                        <div class="mini-line-item unresolved">
                            <span>${summary.line_name || summary.amap_name} [未加载]</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        // 移除之前的展开详情
        document.querySelectorAll('.stop-expanded').forEach(el => el.remove());

        // 在选中站点后插入展开详情
        if (selectedStop) {
            selectedStop.insertAdjacentHTML('afterend', expandedHtml);
        }

    } catch (error) {
        showNotification('加载站点信息失败: ' + error.message, 'error');
    }
}

function closeStopExpanded(stopId) {
    const expanded = document.getElementById(`stop-expanded-${stopId}`);
    if (expanded) {
        expanded.remove();
    }

    const selectedStop = document.getElementById(`line-stop-${stopId}`);
    if (selectedStop) {
        selectedStop.classList.remove('selected');
    }

    // 移除地图上的高亮标记并恢复到全线路视图
    if (lineMapInstance) {
        if (lineMapInstance.getLayer('selected-stop')) {
            lineMapInstance.removeLayer('selected-stop');
            lineMapInstance.removeSource('selected-stop');
        }

        // 恢复到显示整条线路
        const bounds = new maplibregl.LngLatBounds();
        if (lineMapInstance.getSource('line-stops')) {
            const stopsData = lineMapInstance.getSource('line-stops')._data;
            if (stopsData && stopsData.features) {
                stopsData.features.forEach(feature => {
                    bounds.extend(feature.geometry.coordinates);
                });
                if (!bounds.isEmpty()) {
                    lineMapInstance.fitBounds(bounds, { padding: 50 });
                }
            }
        }
    }
}

function renderLineMap(geojson, stopsArray, lineColor = null) {
    if (!lineMapInstance || !geojson) return;

    // 使用线路颜色或默认蓝色
    // 如果颜色不是以#开头，自动添加#
    let routeColor = lineColor || '#000000';
    if (routeColor && !routeColor.startsWith('#')) {
        routeColor = '#' + routeColor;
    }

    // 清理旧图层
    if (lineMapInstance.getLayer('line')) {
        lineMapInstance.removeLayer('line');
    }
    if (lineMapInstance.getLayer('line-stops')) {
        lineMapInstance.removeLayer('line-stops');
    }
    if (lineMapInstance.getSource('line-path')) {
        lineMapInstance.removeSource('line-path');
    }

    // 添加新的线路数据源
    lineMapInstance.addSource('line-path', {
        type: 'geojson',
        data: geojson
    });

    // 添加线路图层
    lineMapInstance.addLayer({
        id: 'line',
        type: 'line',
        source: 'line-path',
        filter: ['==', ['geometry-type'], 'LineString'],
        paint: {
            'line-color': routeColor,
            'line-width': 4
        }
    });

    // 添加站点图层
    lineMapInstance.addLayer({
        id: 'line-stops',
        type: 'circle',
        source: 'line-path',
        filter: ['==', ['geometry-type'], 'Point'],
        paint: {
            'circle-radius': 6,
            'circle-color': routeColor,
            'circle-stroke-width': 2,
            'circle-stroke-color': '#fff'
        }
    });

    // 调整视角
    const bounds = new maplibregl.LngLatBounds();
    geojson.features.forEach(feature => {
        if (feature.geometry.type === 'LineString') {
            feature.geometry.coordinates.forEach(coord => bounds.extend(coord));
        } else if (feature.geometry.type === 'Point') {
            bounds.extend(feature.geometry.coordinates);
        }
    });

    if (!bounds.isEmpty()) {
        lineMapInstance.fitBounds(bounds, { padding: 50 });
    }
}

// 收藏功能
async function toggleFavoriteStop(stopId, btn) {
    try {
        const isFavorite = btn.classList.contains('active');

        if (isFavorite) {
            await apiRequest(`/me/favorite-stops/${stopId}`, { method: 'DELETE' });
            btn.classList.remove('active');
            btn.textContent = '☆';
            showNotification('已取消收藏', 'info');
        } else {
            await apiRequest(`/me/favorite-stops/${stopId}`, { method: 'PUT' });
            btn.classList.add('active');
            btn.textContent = '★';
            showNotification('已收藏', 'success');
        }
    } catch (error) {
        // Error already shown
    }
}

async function toggleFavoriteLine(lineId, btn) {
    try {
        const isFavorite = btn.classList.contains('active');

        if (isFavorite) {
            await apiRequest(`/me/favorite-lines/${lineId}`, { method: 'DELETE' });
            btn.classList.remove('active');
            btn.textContent = '☆';
            showNotification('已取消收藏', 'info');
        } else {
            await apiRequest(`/me/favorite-lines/${lineId}`, { method: 'PUT' });
            btn.classList.add('active');
            btn.textContent = '★';
            showNotification('已收藏', 'success');
        }
    } catch (error) {
        // Error already shown
    }
}

async function loadFavorites() {
    try {
        const stopsData = await apiRequest('/me/favorite-stops?limit=100');
        const favoriteItems = stopsData.items || [];

        document.getElementById('favoriteStops').innerHTML = favoriteItems.length === 0
            ? '<div class="empty-state">暂无收藏站点</div>'
            : favoriteItems.map(item => {
                const stop = item.stop || item;
                return `
                    <div class="stop-item" onclick="showStopDetail(${stop.id}, 'favorite')">
                        <button class="favorite-btn active" onclick="event.stopPropagation(); toggleFavoriteStop(${stop.id}, this)">★</button>
                        <h4>${stop.stop_name}</h4>
                        <p>坐标: ${stop.longitude}, ${stop.latitude}</p>
                    </div>
                `;
            }).join('');

        const linesData = await apiRequest('/me/favorite-lines?limit=100');
        const favoriteLines = linesData.items || [];

        document.getElementById('favoriteLines').innerHTML = favoriteLines.length === 0
            ? '<div class="empty-state">暂无收藏线路</div>'
            : favoriteLines.map(item => {
                const line = item.line || item;
                return `
                    <div class="line-item" onclick="showLineDetail(${line.id})">
                        <button class="favorite-btn active" onclick="event.stopPropagation(); toggleFavoriteLine(${line.id}, this)">★</button>
                        <h4>${line.line_name || line.amap_name}</h4>
                        <p>${line.start_stop_name || ''} → ${line.end_stop_name || ''}</p>
                    </div>
                `;
            }).join('');
    } catch (error) {
        console.error('加载收藏失败:', error);
        showNotification('加载收藏失败', 'error');
    }
}

// 热力图
const STOP_HEATMAP_CLOSE_ZOOM = 12;
const LINE_HEATMAP_CLOSE_ZOOM = 12;
const STOP_HEATMAP_TRANSITION_ZOOM = 4;
const LINE_HEATMAP_TRANSITION_ZOOM = 4;

function heatmapProgress(zoom, closeZoom, transitionZoom) {
    const farZoom = closeZoom - transitionZoom;
    return Math.max(0, Math.min(1, (zoom - farZoom) / transitionZoom));
}

function getStopHeatmapPaint(zoom) {
    const progress = heatmapProgress(
        zoom,
        STOP_HEATMAP_CLOSE_ZOOM,
        STOP_HEATMAP_TRANSITION_ZOOM
    );
    const lerp = (farValue, closeValue) => farValue + (closeValue - farValue) * progress;

    // 站点参数独立维护：保持当前站点图的显示效果。
    return {
        'heatmap-weight': ['*', ['get', 'weight'], lerp(0.55, 1)],
        'heatmap-intensity': lerp(0.5, 0.95),
        'heatmap-color': [
            'interpolate', ['linear'], ['heatmap-density'],
            0, 'rgba(9,31,95,0.7)',
            0.1, 'rgba(9,31,95,0.76)',
            0.25, 'rgba(0,105,148,0.82)',
            0.4, 'rgba(0,156,96,0.86)',
            0.55, 'rgba(102,190,56,0.7)',
            0.7, 'rgba(226,211,29,0.76)',
            0.84, 'rgba(255,133,0,0.84)',
            1, 'rgba(211,32,32,0.9)'
        ],
        'heatmap-radius': lerp(14, 20),
        'heatmap-opacity': lerp(0.89, 0.98)
    };
}

function getLineHeatmapPaint(zoom) {
    const progress = heatmapProgress(
        zoom,
        LINE_HEATMAP_CLOSE_ZOOM,
        LINE_HEATMAP_TRANSITION_ZOOM
    );
    const lerp = (farValue, closeValue) => farValue + (closeValue - farValue) * progress;

    // 线路参数独立维护：线路过红时只调整这里，不影响站点图。
    return {
        'heatmap-weight': ['*', ['get', 'weight'], lerp(0.20, 0.50)],
        'heatmap-intensity': lerp(0.2, 0.35),
        'heatmap-color': [
            'interpolate', ['linear'], ['heatmap-density'],
            0, 'rgba(9,31,95,0.7)',
            0.1, 'rgba(9,31,95,0.76)',
            0.25, 'rgba(0,105,148,0.82)',
            0.4, 'rgba(0,156,96,0.86)',
            0.55, 'rgba(102,190,56,0.7)',
            0.7, 'rgba(226,211,29,0.76)',
            0.84, 'rgba(255,133,0,0.84)',
            1, 'rgba(211,32,32,0.9)'
        ],
        'heatmap-radius': lerp(7, 10),
        'heatmap-opacity': lerp(0.89, 0.98)
    };
}

function getHeatmapPaint(type, zoom) {
    return type === 'stops'
        ? getStopHeatmapPaint(zoom)
        : getLineHeatmapPaint(zoom);
}

async function loadHeatmapData(showSuccess = true) {
    const type = document.getElementById('heatmapType').value;
    const requestedGridSize = Number(document.getElementById('gridSize').value) || 100;

    if (!heatmapInstance) {
        showNotification('地图未初始化', 'error');
        return;
    }

    const bounds = heatmapInstance.getBounds();
    const bbox = `${bounds.getWest()},${bounds.getSouth()},${bounds.getEast()},${bounds.getNorth()}`;
    const zoom = heatmapInstance.getZoom();
    // Finer aggregation at closer zoom levels keeps individual stops and line segments distinct.
    const gridSize = zoom >= 14
        ? Math.min(requestedGridSize, 75)
        : zoom >= 12
            ? Math.min(requestedGridSize, 100)
            : requestedGridSize;

    try {
        const endpoint = type === 'stops'
            ? `/analytics/heatmaps/stops?bbox=${bbox}&grid_size_m=${gridSize}`
            : `/analytics/heatmaps/lines?bbox=${bbox}&grid_size_m=${gridSize}`;

        const response = await apiRequest(endpoint);
        const geojson = response.geojson || response;
        const heatmapPaint = getHeatmapPaint(type, zoom);

        if (!geojson?.features?.length) {
            if (showSuccess) {
                showNotification('当前地图范围内没有可显示的数据，请移动或缩放地图后重试', 'info');
            }
            if (heatmapInstance.getSource('heatmap-data')) {
                heatmapInstance.getSource('heatmap-data').setData(geojson);
            }
            return;
        }

        if (heatmapInstance.getSource('heatmap-data')) {
            heatmapInstance.getSource('heatmap-data').setData(geojson);
            if (heatmapInstance.getLayer('heatmap-layer')) {
                Object.entries(heatmapPaint).forEach(([property, value]) => {
                    heatmapInstance.setPaintProperty('heatmap-layer', property, value);
                });
            }
        } else {
            heatmapInstance.addSource('heatmap-data', {
                type: 'geojson',
                data: geojson
            });

            heatmapInstance.addLayer({
                id: 'heatmap-layer',
                type: 'heatmap',
                source: 'heatmap-data',
                paint: heatmapPaint
            });
        }

        if (showSuccess) {
            showNotification(`热力图加载成功，共 ${geojson.features.length} 个网格`, 'success');
        }
    } catch (error) {
        if (showSuccess) showNotification('加载热力图失败', 'error');
    }
}

document.getElementById('loadHeatmap')?.addEventListener('click', async () => {
    heatmapAutoRefresh = true;
    await loadHeatmapData(true);
});

document.getElementById('heatmapType')?.addEventListener('change', async () => {
    if (heatmapAutoRefresh && heatmapInstance) {
        await loadHeatmapData(false);
    }
});

// 访问统计
const analyticsCharts = new Map();

function getAnalyticsViews(resultId) {
    const result = document.getElementById(resultId);
    return {
        chart: result.querySelector('[data-result-view="chart"]'),
        table: result.querySelector('[data-result-view="table"]')
    };
}

function disposeAnalyticsChart(resultId) {
    const chart = analyticsCharts.get(resultId);
    if (chart) chart.dispose();
    analyticsCharts.delete(resultId);
}

function setAnalyticsState(resultId, message, className) {
    disposeAnalyticsChart(resultId);
    const views = getAnalyticsViews(resultId);
    views.chart.innerHTML = `<div class="${className}">${message}</div>`;
    views.table.innerHTML = `<div class="${className}">${message}</div>`;
}

function createAnalyticsChart(resultId, option, height = 420) {
    const views = getAnalyticsViews(resultId);
    disposeAnalyticsChart(resultId);
    views.chart.innerHTML = '';
    views.chart.style.height = `${height}px`;

    if (typeof echarts === 'undefined') {
        views.chart.innerHTML = '<div class="empty-state">图表组件加载失败，请切换到表格查看</div>';
        return;
    }

    const chart = echarts.init(views.chart);
    chart.setOption(option);
    analyticsCharts.set(resultId, chart);
}

function renderRankingResults(resultId, items, nameKey, nameLabel, countLabel) {
    if (!items.length) {
        setAnalyticsState(resultId, '暂无数据', 'empty-state');
        return;
    }

    const views = getAnalyticsViews(resultId);
    views.table.innerHTML = `<div class="data-table"><table>
        <thead><tr><th>排名</th><th>${nameLabel}</th><th>${countLabel}</th></tr></thead>
        <tbody>${items.map((item, index) => `
            <tr><td>${index + 1}</td><td>${item[nameKey]}</td>
            <td>${item.detail_view_count ?? 0}</td></tr>`).join('')}</tbody>
    </table></div>`;

    const names = items.map(item => item[nameKey]);
    const counts = items.map(item => item.detail_view_count ?? 0);
    createAnalyticsChart(resultId, {
        color: ['#1976d2'],
        grid: { top: 24, right: 72, bottom: 36, left: 24, containLabel: true },
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: params => `${params[0].name}<br>${countLabel}：${params[0].value}`
        },
        xAxis: {
            type: 'value',
            minInterval: 1,
            name: '访问次数',
            splitLine: { lineStyle: { color: '#edf0f3' } }
        },
        yAxis: {
            type: 'category',
            inverse: true,
            data: names,
            axisLabel: { width: 180, overflow: 'truncate' },
            axisTick: { show: false }
        },
        series: [{
            type: 'bar',
            data: counts,
            barMaxWidth: 22,
            label: { show: true, position: 'right', color: '#444' },
            emphasis: { itemStyle: { color: '#125ca6' } }
        }]
    }, Math.max(420, items.length * 34 + 90));
}

function renderDistributionResults(items, bucket) {
    const resultId = 'distributionResults';
    if (!items.length) {
        setAnalyticsState(resultId, '暂无数据', 'empty-state');
        return;
    }

    const bucketLabel = bucket === 'hour' ? '小时' : bucket === 'day' ? '日期' : '星期/小时';
    const views = getAnalyticsViews(resultId);
    views.table.innerHTML = `<div class="data-table"><table>
        <thead><tr><th>${bucketLabel}</th><th>访问次数</th></tr></thead>
        <tbody>${items.map(item => `<tr>
            <td>${item.bucket ?? item.time_bucket ?? ''}</td>
            <td>${item.detail_view_count ?? item.count ?? item.view_count ?? 0}</td>
        </tr>`).join('')}</tbody>
    </table></div>`;

    if (bucket === 'weekday_hour') {
        const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
        const heatmapData = items.map(item => {
            const [weekday, hour] = String(item.bucket).split('-').map(Number);
            return [hour, weekday, item.detail_view_count ?? 0];
        });
        const maxValue = Math.max(1, ...heatmapData.map(item => item[2]));
        createAnalyticsChart(resultId, {
            tooltip: { formatter: params => `${weekdays[params.value[1]]} ${String(params.value[0]).padStart(2, '0')}:00<br>访问次数：${params.value[2]}` },
            grid: { top: 24, right: 42, bottom: 76, left: 64 },
            xAxis: { type: 'category', data: Array.from({ length: 24 }, (_, hour) => `${String(hour).padStart(2, '0')}:00`), splitArea: { show: true } },
            yAxis: { type: 'category', data: weekdays, splitArea: { show: true } },
            visualMap: { min: 0, max: maxValue, calculable: true, orient: 'horizontal', left: 'center', bottom: 8, inRange: { color: ['#edf5fd', '#78b4e8', '#1976d2'] } },
            series: [{ type: 'heatmap', data: heatmapData, emphasis: { itemStyle: { borderColor: '#333', borderWidth: 1 } } }]
        });
        return;
    }

    const labels = items.map(item => bucket === 'hour'
        ? `${String(item.bucket).padStart(2, '0')}:00`
        : String(item.bucket));
    const counts = items.map(item => item.detail_view_count ?? item.count ?? item.view_count ?? 0);
    createAnalyticsChart(resultId, {
        color: ['#1976d2'],
        grid: { top: 30, right: 36, bottom: 62, left: 58 },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: labels, axisLabel: { rotate: bucket === 'day' ? 35 : 0, hideOverlap: true } },
        yAxis: { type: 'value', minInterval: 1, name: '访问次数', splitLine: { lineStyle: { color: '#edf0f3' } } },
        series: [{ type: 'line', data: counts, smooth: true, symbolSize: 7, areaStyle: { color: 'rgba(25, 118, 210, 0.12)' } }]
    });
}

document.querySelectorAll('.view-switch').forEach(viewSwitch => {
    viewSwitch.addEventListener('click', event => {
        const button = event.target.closest('.view-switch-btn');
        if (!button) return;
        viewSwitch.querySelectorAll('.view-switch-btn').forEach(item => item.classList.remove('active'));
        button.classList.add('active');
        const views = getAnalyticsViews(viewSwitch.dataset.target);
        const showChart = button.dataset.view === 'chart';
        views.chart.hidden = !showChart;
        views.table.hidden = showChart;
        if (showChart) analyticsCharts.get(viewSwitch.dataset.target)?.resize();
    });
});

window.addEventListener('resize', () => {
    analyticsCharts.forEach(chart => chart.resize());
});

document.getElementById('loadPopularity')?.addEventListener('click', async () => {
    const startTime = document.getElementById('popStartTime').value;
    const endTime = document.getElementById('popEndTime').value;
    const limit = document.getElementById('popLimit').value;

    setAnalyticsState('popularityResults', '正在加载', 'loading');
    try {
        const params = new URLSearchParams({ limit: limit || 20 });
        if (startTime) params.append('start_at', startTime);
        if (endTime) params.append('end_at', endTime);

        const data = await apiRequest(`/analytics/stops/popularity?${params}`);
        const stops = data.items || data.stops || data.data || [];

        renderRankingResults('popularityResults', stops, 'stop_name', '站点名称', '站点详情访问次数');
    } catch (error) {
        setAnalyticsState('popularityResults', '加载失败', 'empty-state');
    }
});

document.getElementById('loadLinePopularity')?.addEventListener('click', async () => {
    const startTime = document.getElementById('linePopStartTime').value;
    const endTime = document.getElementById('linePopEndTime').value;
    const limit = document.getElementById('linePopLimit').value;
    setAnalyticsState('linePopularityResults', '正在加载', 'loading');
    try {
        const params = new URLSearchParams({ limit: limit || 20 });
        if (startTime) params.append('start_at', startTime);
        if (endTime) params.append('end_at', endTime);
        const data = await apiRequest(`/analytics/lines/popularity?${params}`);
        const lines = data.items || [];
        renderRankingResults('linePopularityResults', lines, 'line_name', '线路名称', '线路详情访问次数');
    } catch (error) {
        setAnalyticsState('linePopularityResults', '加载失败', 'empty-state');
    }
});

document.getElementById('loadDistribution')?.addEventListener('click', async () => {
    const targetType = document.getElementById('distTargetType').value;
    const targetName = document.getElementById('distTargetName').value.trim();
    const startTime = document.getElementById('distStartTime').value;
    const endTime = document.getElementById('distEndTime').value;
    const bucket = document.getElementById('distBucket').value;

    if (!targetName) {
        showNotification(`请输入${targetType === 'stop' ? '车站' : '线路'}名称`, 'error');
        return;
    }

    setAnalyticsState('distributionResults', '正在加载', 'loading');
    try {
        const params = new URLSearchParams({ bucket });
        if (startTime) params.append('start_at', startTime);
        if (endTime) params.append('end_at', endTime);

        params.append('name', targetName);
        if (targetType === 'line') params.append('actor_scope', 'all');
        const endpoint = targetType === 'stop'
            ? '/analytics/stops/view-distribution-by-name'
            : '/analytics/lines/view-distribution-by-name';
        const data = await apiRequest(`${endpoint}?${params}`);
        const distribution = data.items || data.distribution || data.data || [];

        renderDistributionResults(distribution, bucket);
    } catch (error) {
        setAnalyticsState('distributionResults', '加载失败', 'empty-state');
    }
});

document.getElementById('distTargetType')?.addEventListener('change', (event) => {
    const input = document.getElementById('distTargetName');
    input.placeholder = event.target.value === 'stop' ? '输入车站名称' : '输入线路名称';
});

// 用户管理
document.getElementById('createUserBtn')?.addEventListener('click', () => {
    document.getElementById('userModalTitle').textContent = '创建用户';
    document.getElementById('userForm').reset();
    document.getElementById('userForm').onsubmit = async (e) => {
        e.preventDefault();

        const username = document.getElementById('userUsername').value;
        const password = document.getElementById('userPassword').value;
        const role = document.getElementById('userRole').value;

        try {
            await apiRequest('/admin/users', {
                method: 'POST',
                body: JSON.stringify({ username, password, role })
            });

            showNotification('用户创建成功', 'success');
            document.getElementById('userModal').classList.remove('show');
            loadUsers();
        } catch (error) {
            // Error already shown
        }
    };

    document.getElementById('userModal').classList.add('show');
});

async function loadUsers() {
    try {
        const data = await apiRequest('/admin/users?limit=100');
        const users = data.items || data.users || data.data || [];

        document.getElementById('usersTable').innerHTML = `<div class="data-table"><table>
            <thead>
                <tr>
                    <th>用户名</th>
                    <th>角色</th>
                    <th>状态</th>
                    <th>创建时间</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                ${users.map(user => `
                    <tr>
                        <td>${user.username}</td>
                        <td>${getRoleName(user.role)}</td>
                        <td>${user.is_active ? '启用' : '停用'}</td>
                        <td>${new Date(user.created_at).toLocaleString('zh-CN')}</td>
                        <td>
                            <button class="btn btn-secondary" onclick="toggleUserStatus(${user.id}, ${user.is_active})">
                                ${user.is_active ? '停用' : '启用'}
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table></div>`;
    } catch (error) {
        document.getElementById('usersTable').innerHTML = '<div class="empty-state">加载失败</div>';
    }
}

async function toggleUserStatus(userId, isActive) {
    try {
        await apiRequest(`/admin/users/${userId}`, {
            method: 'PATCH',
            body: JSON.stringify({ is_active: !isActive })
        });

        showNotification('用户状态更新成功', 'success');
        loadUsers();
    } catch (error) {
        // Error already shown
    }
}

// 导入记录
async function loadIngestionRuns() {
    try {
        const data = await apiRequest('/admin/ingestion-runs?limit=100');
        const runs = data.items || data.runs || data.data || [];

        document.getElementById('ingestionTable').innerHTML = runs.length === 0
            ? '<div class="empty-state">暂无导入记录</div>'
            : `<div class="data-table"><table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>接口</th>
                        <th>触发方式</th>
                        <th>关键词</th>
                        <th>状态</th>
                        <th>接收/插入/更新/失败</th>
                        <th>开始时间</th>
                    </tr>
                </thead>
                <tbody>
                    ${runs.map(run => `
                        <tr>
                            <td>${run.id}</td>
                            <td>${run.endpoint}</td>
                            <td>${run.trigger_type}</td>
                            <td>${run.request_keyword || 'N/A'}</td>
                            <td>${run.status}</td>
                            <td>${run.received_count}/${run.inserted_count}/${run.updated_count}/${run.failed_count}</td>
                            <td>${new Date(run.started_at).toLocaleString('zh-CN')}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table></div>`;
    } catch (error) {
        document.getElementById('ingestionTable').innerHTML = '<div class="empty-state">加载失败</div>';
    }
}

// 模态框关闭
document.querySelectorAll('.modal .close').forEach(closeBtn => {
    closeBtn.addEventListener('click', () => {
        const modal = closeBtn.closest('.modal');
        modal.classList.remove('show');

        // 清理展开的站点详情和选中状态
        document.querySelectorAll('.stop-expanded').forEach(el => el.remove());
        document.querySelectorAll('.stop-item.selected').forEach(el => el.classList.remove('selected'));

        // 清除地图上的高亮标记
        if (lineMapInstance && lineMapInstance.getLayer('selected-stop')) {
            lineMapInstance.removeLayer('selected-stop');
            lineMapInstance.removeSource('selected-stop');
        }
    });
});

window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('show');

        // 清理展开的站点详情和选中状态
        document.querySelectorAll('.stop-expanded').forEach(el => el.remove());
        document.querySelectorAll('.stop-item.selected').forEach(el => el.classList.remove('selected'));

        // 清除地图上的高亮标记
        if (lineMapInstance && lineMapInstance.getLayer('selected-stop')) {
            lineMapInstance.removeLayer('selected-stop');
            lineMapInstance.removeSource('selected-stop');
        }
    }
});

// 初始化
if (token) {
    loadCurrentUser();
} else {
    document.getElementById('authPage').style.display = 'block';
}
