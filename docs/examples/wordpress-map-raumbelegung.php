<?php
/**
 * Plugin Name: MAP Raumbelegung
 * Description: Zeigt öffentliche, aggregierte MAP-Belegungstage mit [map_raumbelegung].
 * Version: 1.1.0
 */
if (!defined('ABSPATH')) { exit; }

function map_public_room_occupancy_shortcode() {
    // Erst nach einem entsprechenden Prod-Update auf https://map.example.org umstellen.
    $base_url = 'https://dev.map.example.org/api/v1/rooms/occupancy/';
    $start = current_datetime()->setTime(0, 0);
    $end = $start->modify('+89 days');
    $url = add_query_arg(array('start' => $start->format('Y-m-d'), 'end' => $end->format('Y-m-d')), $base_url);
    $cache_key = 'map_rooms_day2_' . substr(hash('sha256', $url), 0, 32);
    $payload = get_transient($cache_key);
    if (false === $payload) {
        $response = wp_remote_get($url, array('timeout' => 5, 'redirection' => 0, 'limit_response_size' => 262144, 'headers' => array('Accept' => 'application/json')));
        if (is_wp_error($response) || 200 !== wp_remote_retrieve_response_code($response)) {
            return '<p>Die Raumbelegung ist momentan nicht verfügbar.</p>';
        }
        $payload = json_decode(wp_remote_retrieve_body($response), true);
        if (!is_array($payload) || !isset($payload['version']) || 1 !== $payload['version'] || !isset($payload['days']) || !is_array($payload['days'])) {
            return '<p>Die Raumbelegung konnte nicht geladen werden.</p>';
        }
        set_transient($cache_key, $payload, MINUTE_IN_SECONDS);
    }
    if (!isset($payload['aggregation']) || 'continuous_full_day' !== $payload['aggregation']) { return '<p>Die Belegungsschnittstelle muss aktualisiert werden.</p>'; }
    if (empty($payload['days'])) { return '<p>Im angezeigten Zeitraum sind keine Belegungen eingetragen.</p>'; }
    $html = '<div class="map-room-occupancy"><table><caption>Raumbelegung der nächsten 90 Tage</caption><thead><tr><th scope="col">Tag</th><th scope="col">Belegung</th><th scope="col">Status</th><th scope="col">Räume</th></tr></thead><tbody>';
    foreach ($payload['days'] as $day) {
        if (!is_array($day) || !isset($day['date'], $day['occupancy'], $day['statuses']) || !is_string($day['date']) || !preg_match('/^\d{4}-\d{2}-\d{2}$/D', $day['date']) || !is_string($day['occupancy']) || !is_array($day['statuses'])) { continue; }
        $date = DateTimeImmutable::createFromFormat('!Y-m-d', $day['date'], wp_timezone());
        if (!$date || $date->format('Y-m-d') !== $day['date']) { continue; }
        $levels = array('full' => 'Alle Räume ganztägig belegt', 'partial' => 'Teilweise belegt');
        if (!isset($levels[$day['occupancy']])) { continue; }
        $statuses = array();
        if (in_array('approved', $day['statuses'], true)) { $statuses[] = 'Genehmigt'; }
        if (in_array('pending', $day['statuses'], true)) { $statuses[] = 'Schwebend'; }
        $room_names = isset($day['rooms']) && is_array($day['rooms']) ? array_filter($day['rooms'], 'is_string') : array();
        $html .= '<tr><th scope="row">' . esc_html(wp_date('d.m.Y', $date->getTimestamp(), wp_timezone())) . '</th><td>' . esc_html($levels[$day['occupancy']]) . '</td><td>' . esc_html(implode(' / ', $statuses)) . '</td><td>' . esc_html(implode(', ', $room_names)) . '</td></tr>';
    }
    $html .= '</tbody></table><p><small>„Alle Räume ganztägig belegt“ bedeutet: Jeder aktive Raum ist den gesamten lokalen Kalendertag lückenlos belegt. Teilzeitbelegungen, etwa nur bis 18 Uhr, werden als teilweise angezeigt. Die Raumliste nennt alle irgendwann an dem Tag betroffenen Räume. Schwebende Anfragen sind noch nicht genehmigt. Freie Zeitfenster bitte bei den Verantwortlichen erfragen.</small></p></div>';
    return $html;
}
add_shortcode('map_raumbelegung', 'map_public_room_occupancy_shortcode');
