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

  function initSidebarActiveState() {
    var sidebar = qs('#sidebar');
    if (!sidebar) return;

    var links = Array.prototype.slice.call(
      sidebar.querySelectorAll('.sidebar-menu a.menu-item, .sidebar-menu a.menu-subitem')
    );
    if (!links.length) return;

    var currentPath = window.location && window.location.pathname ? window.location.pathname : '';
    if (!currentPath) return;

    var best = null;
    var bestLen = -1;

    links.forEach(function (a) {
      if (!a || !a.getAttribute) return;
      var href = a.getAttribute('href');
      if (!href) return;
      if (href.indexOf('http') === 0) return;

      var linkPath = '';
      try {
        linkPath = new URL(href, window.location.origin).pathname;
      } catch (e) {
        linkPath = href;
      }

      if (!linkPath || linkPath === '#') return;

      var isAdminRoot = linkPath === '/admin/' || linkPath === '/admin';
      if (isAdminRoot) {
        if (currentPath === '/admin/' || currentPath === '/admin') {
          if (linkPath.length > bestLen) {
            best = a;
            bestLen = linkPath.length;
          }
        }
        return;
      }

      if (currentPath === linkPath || currentPath.indexOf(linkPath + '/') === 0) {
        if (linkPath.length > bestLen) {
          best = a;
          bestLen = linkPath.length;
        }
      }
    });

    if (!best) return;

    best.classList.add('active');
    best.setAttribute('aria-current', 'page');

    var details = best.closest('details.menu-group');
    if (details) {
      details.open = true;
      var summary = details.querySelector('summary.menu-item');
      if (summary) summary.classList.add('active');
    }
  }

  function initSidebarCollapse() {
    var btn = qs('#toggle-btn');
    var btnMobile = qs('#toggle-btn-mobile');
    var sidebar = qs('#sidebar');
    if ((!btn && !btnMobile) || !sidebar) return;

    var backdrop = document.querySelector('.sidebar-backdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.className = 'sidebar-backdrop';
      document.body.appendChild(backdrop);
    }

    function isMobile() {
      return window.matchMedia && window.matchMedia('(max-width: 1024px)').matches;
    }

    function openMobile() {
      sidebar.classList.add('mobile-open');
      backdrop.classList.add('open');
      document.body.classList.add('sidebar-mobile-open');
    }

    function closeMobile() {
      sidebar.classList.remove('mobile-open');
      backdrop.classList.remove('open');
      document.body.classList.remove('sidebar-mobile-open');
    }

    function toggleMobile() {
      if (sidebar.classList.contains('mobile-open')) closeMobile();
      else openMobile();
    }

    if (btn) {
      btn.addEventListener('click', function () {
        if (isMobile()) {
          toggleMobile();
          return;
        }

        closeMobile();
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

    if (btnMobile) {
      btnMobile.addEventListener('click', function () {
        toggleMobile();
      });
    }

    backdrop.addEventListener('click', closeMobile);

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeMobile();
    });

    sidebar.addEventListener('click', function (e) {
      if (!isMobile()) return;
      var a = e.target && e.target.closest ? e.target.closest('a') : null;
      if (a) closeMobile();
    });

    window.addEventListener('resize', function () {
      if (!isMobile()) closeMobile();
    });
  }

  function init() {
    initTheme();
    initThemeToggle();
    initSidebarCollapse();
    initUserMenu();
    initSidebarActiveState();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
