(function () {
  function qs(sel) {
    return document.querySelector(sel);
  }

  function initUserMenu() {
    var toggle = qs('#user-menu-toggle');
    var menu = qs('#user-menu');
    if (!toggle || !menu) return;

    var wrapper = toggle.parentElement;
    if (!wrapper) return;

    function isOpen() {
      return wrapper.classList.contains('open');
    }

    function openMenu() {
      wrapper.classList.add('open');
      toggle.setAttribute('aria-expanded', 'true');
    }

    function closeMenu() {
      wrapper.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }

    function toggleMenu() {
      if (isOpen()) closeMenu();
      else openMenu();
    }

    toggle.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      toggleMenu();
    });

    toggle.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleMenu();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        closeMenu();
      }
    });

    document.addEventListener('click', function (e) {
      if (!isOpen()) return;
      if (wrapper.contains(e.target)) return;
      closeMenu();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeMenu();
    });
  }

  function initTheme() {
    var key = 'darkTheme';
    var saved = null;
    try {
      saved = localStorage.getItem(key);
    } catch (e) { }

    if (saved === 'false') {
      document.body.classList.remove('dark-theme');
    } else if (saved === 'true') {
      document.body.classList.add('dark-theme');
    }

    updateThemeToggleUI();
  }

  function updateThemeToggleUI() {
    var toggle = qs('#theme-toggle');
    if (!toggle) return;
    var icon = toggle.querySelector('i');
    var text = toggle.querySelector('.theme-text');
    if (!icon || !text) return;

    var isDark = document.body.classList.contains('dark-theme');
    if (isDark) {
      icon.className = 'fas fa-moon';
      text.textContent = 'تم تیره';
    } else {
      icon.className = 'fas fa-sun';
      text.textContent = 'تم روشن';
    }
  }

  function toggleTheme() {
    document.body.classList.toggle('dark-theme');
    var isDark = document.body.classList.contains('dark-theme');
    try {
      localStorage.setItem('darkTheme', String(isDark));
    } catch (e) { }
    updateThemeToggleUI();
  }

  function initThemeToggle() {
    var toggle = qs('#theme-toggle');
    if (!toggle) return;
    toggle.addEventListener('click', toggleTheme);
    toggle.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleTheme();
      }
    });
  }

  function initSidebarCollapse() {
    var btn = qs('#toggle-btn');
    var sidebar = qs('#sidebar');
    if (!btn || !sidebar) return;

    btn.addEventListener('click', function () {
      sidebar.classList.toggle('collapsed');
      var icon = btn.querySelector('i');
      if (!icon) return;
      if (sidebar.classList.contains('collapsed')) {
        icon.classList.remove('fa-chevron-right');
        icon.classList.add('fa-chevron-left');
      } else {
        icon.classList.remove('fa-chevron-left');
        icon.classList.add('fa-chevron-right');
      }
    });
  }

  function init() {
    initTheme();
    initThemeToggle();
    initSidebarCollapse();
    initUserMenu();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
