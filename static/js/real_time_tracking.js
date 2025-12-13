// Real-time tracking JavaScript

let map;
let currentMarker = null;
let pathLayer = null;
let geofenceLayers = [];
let isTracking = false;
let lastUpdate = null;
let connectionStartTime = null;
let updateInterval;
let pathCoordinates = [];

// These variables are set in the template
// const deviceId;
// const deviceName;
// const locationsUrl;
// const initialLocations;

function initMap() {
    // Default to Tehran coordinates if no locations
    let defaultLat = 35.6892;
    let defaultLng = 51.3890;

    if (initialLocations && initialLocations.length > 0) {
        const latest = initialLocations[initialLocations.length - 1];
        defaultLat = latest.latitude;
        defaultLng = latest.longitude;
    }

    map = L.map('map').setView([defaultLat, defaultLng], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Initialize with initial locations
    if (initialLocations && initialLocations.length > 0) {
        initialLocations.forEach(loc => {
            pathCoordinates.push([loc.latitude, loc.longitude]);
        });
        updatePath();
        const latest = initialLocations[initialLocations.length - 1];
        updateCurrentPosition(latest.latitude, latest.longitude, new Date(latest.timestamp).toLocaleString('fa-IR'), latest.speed, latest.battery_level);
    }

    // Load geofences (if implemented)
    loadGeofences();
}

// Update current position
function updateCurrentPosition(lat, lng, timestamp, speed = null, battery = null) {
    // Remove previous marker
    if (currentMarker) {
        map.removeLayer(currentMarker);
    }

    // Add new marker
    currentMarker = L.circleMarker([lat, lng], {
        color: '#28a745',
        fillColor: '#28a745',
        fillOpacity: 1,
        radius: 8,
        weight: 2
    }).addTo(map);

    currentMarker.bindPopup(`
        <b>${deviceName}</b><br>
        موقعیت: ${lat.toFixed(6)}, ${lng.toFixed(6)}<br>
        زمان: ${timestamp}
        ${speed ? `<br>سرعت: ${speed} km/h` : ''}
        ${battery ? `<br>باتری: ${battery}%` : ''}
    `);

    // Add to path
    pathCoordinates.push([lat, lng]);

    // Update path
    updatePath();

    // Update status panel
    document.getElementById('current-position').textContent = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    document.getElementById('last-update').textContent = timestamp;
    document.getElementById('connection-status').textContent = 'آنلاین';
    document.getElementById('connection-status').className = 'status-value status-online';

    if (speed !== null) {
        document.getElementById('current-speed').textContent = `${speed} km/h`;
    }

    if (battery !== null) {
        document.getElementById('battery-level').textContent = `${battery}%`;
    }

    lastUpdate = new Date();
}

// Update path
function updatePath() {
    if (pathLayer) {
        map.removeLayer(pathLayer);
    }

    if (pathCoordinates.length > 1) {
        pathLayer = L.polyline(pathCoordinates, {
            color: '#007bff',
            weight: 4,
            opacity: 0.8
        }).addTo(map);
    }
}

// Load geofences
function loadGeofences() {
    // Implement if needed
}

// Start real-time tracking
function startTracking() {
    if (isTracking) return;

    isTracking = true;
    connectionStartTime = new Date();

    document.getElementById('btn-start').classList.remove('active');
    document.getElementById('btn-stop').classList.add('active');
    document.getElementById('live-indicator').style.display = 'block';

    updateConnectionTime();

    // Set up polling for updates
    updateInterval = setInterval(() => {
        fetchLatestLocation();
    }, 10000); // Update every 10 seconds

    // Initial fetch
    fetchLatestLocation();
}

// Stop tracking
function stopTracking() {
    if (!isTracking) return;

    isTracking = false;

    document.getElementById('btn-stop').classList.remove('active');
    document.getElementById('btn-start').classList.add('active');
    document.getElementById('live-indicator').style.display = 'none';

    if (updateInterval) {
        clearInterval(updateInterval);
    }

    document.getElementById('connection-status').textContent = 'آفلاین';
    document.getElementById('connection-status').className = 'status-value status-offline';
}

// Fetch latest location
function fetchLatestLocation() {
    fetch(`${locationsUrl}?hours=1&limit=1`)
        .then(response => response.json())
        .then(data => {
            if (data.locations && data.locations.length > 0) {
                const location = data.locations[0];
                // Check if this is a new location
                if (pathCoordinates.length === 0 ||
                    pathCoordinates[pathCoordinates.length - 1][0] !== location.latitude ||
                    pathCoordinates[pathCoordinates.length - 1][1] !== location.longitude) {
                    updateCurrentPosition(
                        location.latitude,
                        location.longitude,
                        new Date(location.timestamp).toLocaleString('fa-IR'),
                        location.speed,
                        location.battery_level
                    );
                }
            }
        })
        .catch(error => {
            console.error('Error fetching location:', error);
            document.getElementById('connection-status').textContent = 'خطا در اتصال';
            document.getElementById('connection-status').className = 'status-value status-offline';
        });
}

// Update connection time
function updateConnectionTime() {
    if (!connectionStartTime || !isTracking) {
        document.getElementById('connection-time').textContent = '-';
        return;
    }

    const now = new Date();
    const diff = Math.floor((now - connectionStartTime) / 1000);

    const hours = Math.floor(diff / 3600);
    const minutes = Math.floor((diff % 3600) / 60);
    const seconds = diff % 60;

    document.getElementById('connection-time').textContent =
        `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

// Center map on current position
function centerMap() {
    if (currentMarker) {
        map.setView(currentMarker.getLatLng(), 15);
    }
}

// Toggle fullscreen
function toggleFullscreen() {
    const container = document.querySelector('.real-time-container');

    if (!document.fullscreenElement) {
        container.requestFullscreen().catch(err => {
            console.error('Error attempting to enable fullscreen:', err);
        });
    } else {
        document.exitFullscreen();
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('map')) {
        initMap();
    }

    // Control buttons
    document.getElementById('btn-start').addEventListener('click', function (e) {
        e.preventDefault();
        startTracking();
    });

    document.getElementById('btn-stop').addEventListener('click', function (e) {
        e.preventDefault();
        stopTracking();
    });

    document.getElementById('btn-center').addEventListener('click', function (e) {
        e.preventDefault();
        centerMap();
    });

    document.getElementById('btn-fullscreen').addEventListener('click', function (e) {
        e.preventDefault();
        toggleFullscreen();
    });

    // Update connection time every second
    setInterval(updateConnectionTime, 1000);

    // Alert notification click
    document.getElementById('alert-notification').addEventListener('click', function () {
        this.classList.remove('show');
    });

    // Handle fullscreen changes
    document.addEventListener('fullscreenchange', function () {
        const btn = document.getElementById('btn-fullscreen');
        const icon = btn.querySelector('i');

        if (document.fullscreenElement) {
            icon.className = 'fas fa-compress';
        } else {
            icon.className = 'fas fa-expand';
        }
    });
});

// Cleanup on page unload
window.addEventListener('beforeunload', function () {
    stopTracking();
});

// Handle visibility change
document.addEventListener('visibilitychange', function () {
    if (document.hidden && isTracking) {
        // Could pause updates
    }
});