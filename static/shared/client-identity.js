/**
 * Anonymous client/page identifiers for observability.
 *
 * client_id persists in localStorage to link sessions from the same browser.
 * page_session_id is regenerated per page load to group multiple requests made
 * while the user stays on one page.
 */
(function () {
    const CLIENT_KEY = 'minicpmo_client_id';

    function randomId(prefix) {
        const rand = (typeof crypto !== 'undefined' && crypto.randomUUID)
            ? crypto.randomUUID().replace(/-/g, '').slice(0, 12)
            : Math.random().toString(36).slice(2, 14);
        return `${prefix}_${Date.now().toString(36)}_${rand}`;
    }

    function getClientId() {
        try {
            let id = localStorage.getItem(CLIENT_KEY);
            if (!id) {
                id = randomId('c');
                localStorage.setItem(CLIENT_KEY, id);
            }
            return id;
        } catch {
            return randomId('c_tmp');
        }
    }

    const pageSessionId = randomId('p');

    function getPageSessionId() {
        return pageSessionId;
    }

    function getClientSurface() {
        const path = location.pathname || '';
        if (path.startsWith('/mobile-omni')) return 'mobile_omni';
        if (path.startsWith('/mobile')) return 'mobile';
        if (path.startsWith('/realtime')) return 'realtime_demo';
        if (path.startsWith('/omni') || path.startsWith('/audio_duplex') || path.startsWith('/half_duplex') || path.startsWith('/turnbased')) {
            return 'desktop';
        }
        return 'unknown';
    }

    function appendToUrl(url) {
        try {
            const u = new URL(url, location.href);
            u.searchParams.set('client_id', getClientId());
            u.searchParams.set('page_session_id', getPageSessionId());
            u.searchParams.set('page_route', location.pathname || '/');
            u.searchParams.set('client_surface', getClientSurface());
            return u.toString();
        } catch {
            const sep = url.includes('?') ? '&' : '?';
            return `${url}${sep}client_id=${encodeURIComponent(getClientId())}&page_session_id=${encodeURIComponent(getPageSessionId())}&page_route=${encodeURIComponent(location.pathname || '/')}&client_surface=${encodeURIComponent(getClientSurface())}`;
        }
    }

    window.ClientIdentity = {
        getClientId,
        getPageSessionId,
        getClientSurface,
        appendToUrl,
    };
})();
