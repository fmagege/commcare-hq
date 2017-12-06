/* globals window */
/**
 * Instatiates the Hubspot analytics platform.
 */
hqDefine('analytix/js/hubspot', [
    'underscore',
    'analytix/js/initial',
    'analytix/js/logging',
    'analytix/js/utils',
], function (
    _,
    initialAnalytics,
    logging,
    utils
) {
    'use strict';
    var _get = initialAnalytics.getFn('hubspot'),
        _global = initialAnalytics.getFn('global'),
        _logger;

    var _hsq = window._hsq = window._hsq || [];

    $(function () {
        _logger = logging.getLoggerForApi('Hubspot');
        if (_global('isEnabled')) {
            var apiId = _get('apiId');
            if (apiId) {
                var scriptSrc = '//js.hs-analytics.net/analytics/' + utils.getDateHash() + '/' + apiId + '.js';
                utils.insertScript(scriptSrc, _logger.debug.log, {
                    id: 'hs-analytics',
                });
            }
            _logger.debug.log('Initialized');
        }
    });

    /**
     * Sends data to Hubspot to identify the current session.
     * @param {object} data
     */
    var identify = function (data) {
        _logger.debug.log(data, "Identify");
        _hsq.push(['identify', data]);
    };

    /**
     * Tracks an event through the Hubspot API
     * @param {string} eventId - The ID of the event. If you created the event in HubSpot, use the numerical ID of the event.
     * @param {integer|float} value - This is an optional argument that can be used to track the revenue of an event.
     */
    var trackEvent = function (eventId, value) {
        if (_global('isEnabled')) {
            _logger.debug.log(_logger.fmt.labelArgs(["Event ID", "Value"], arguments), 'Track Event');
            _hsq.push(['trackEvent', {
                id: eventId,
                value: value,
            }]);
        }
    };

    return {
        identify: identify,
        trackEvent: trackEvent,
    };
});
