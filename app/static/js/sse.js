/**
 * FoodLoop ID — realtime client for the Server-Sent Events endpoint.
 *
 * Consumes the `surplus_new`, `claim_update`, `expiry_alert`, and `kpi_update`
 * events streamed by `GET /events` and refreshes the notification badge, the
 * KPI cards, and the toast area without reloading the page.
 */
(function () {
  'use strict';

  var ENDPOINT = '/events';

  function parsePayload(event) {
    try {
      return JSON.parse(event.data);
    } catch (err) {
      return {};
    }
  }

  function toast(message, type) {
    if (typeof window.showToast === 'function') {
      window.showToast(message, type);
    }
  }

  function updateBadge(count) {
    if (typeof count !== 'number') {
      return;
    }
    var visible = count > 0 ? '' : 'none';
    var badge = document.getElementById('notif-badge');
    if (badge) {
      badge.textContent = String(count);
      badge.style.display = visible;
    }
    var dot = document.getElementById('notif-dot');
    if (dot) {
      dot.style.display = visible;
    }
    var link = document.getElementById('notif-link');
    if (link) {
      link.setAttribute(
        'aria-label',
        count > 0 ? 'Notifikasi (' + count + ' belum dibaca)' : 'Notifikasi'
      );
    }
  }

  function applyKpis(payload) {
    var cards = payload.kpis || [];
    cards.forEach(function (kpi) {
      if (!kpi || !kpi.key) {
        return;
      }
      var node = document.querySelector('[data-kpi="' + kpi.key + '"]');
      if (node) {
        node.textContent = kpi.value;
      }
    });
  }

  function emit(name, detail) {
    window.dispatchEvent(new CustomEvent(name, { detail: detail }));
  }

  function connect() {
    if (!('EventSource' in window)) {
      return;
    }

    var source = new EventSource(ENDPOINT, { withCredentials: true });

    source.addEventListener('open', function () {
      document.body.setAttribute('data-sse', 'connected');
    });

    source.addEventListener('surplus_new', function (event) {
      var data = parsePayload(event);
      toast('Surplus baru: ' + data.title + ' di ' + data.city, 'info');
      updateBadge(data.unread_count);
      emit('foodloop:surplus_new', data);
    });

    source.addEventListener('claim_update', function (event) {
      var data = parsePayload(event);
      var tone = data.status === 'cancelled' ? 'danger' : 'success';
      toast('Klaim ' + data.status_label + ': ' + data.listing_title, tone);
      updateBadge(data.unread_count);
      emit('foodloop:claim_update', data);
    });

    source.addEventListener('expiry_alert', function (event) {
      var data = parsePayload(event);
      toast('Segera pakai: ' + data.name + ' (' + data.days_label + ')', 'warning');
      updateBadge(data.unread_count);
      emit('foodloop:expiry_alert', data);
    });

    source.addEventListener('kpi_update', function (event) {
      var data = parsePayload(event);
      applyKpis(data);
      emit('foodloop:kpi', data);
    });

    source.addEventListener('error', function () {
      document.body.setAttribute('data-sse', 'reconnecting');
    });

    window.addEventListener('beforeunload', function () {
      source.close();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', connect);
  } else {
    connect();
  }
})();
