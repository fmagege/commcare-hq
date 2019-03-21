hqDefine('app_manager/js/manage_releases', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/widgets_v4', // using select2/dist/js/select2.full.min for ko-select2 on location select
], function (
    $,
    ko,
    _,
    initialPageData,
    assertProperties,
) {
    'use strict';
    $(function () {
        var enabledAppRelease = function (details) {
            var self = {};
            assertProperties.assert(details, [], ['id', 'build_id', 'active', 'app', 'version', 'location',
                                                  'activated_on', 'deactivated_on']);
            self.id = details.id;
            self.build_id = details.build_id;
            self.active = ko.observable(details.active);
            self.app = details.app;
            self.version = details.version;
            self.location = details.location;
            self.activatedOn = ko.observable(details.activated_on);
            self.deactivatedOn = ko.observable(details.deactivated_on);
            self.errorMessage = ko.observable();
            self.domId = "restriction_" + self.id;
            self.ajaxInProgress = ko.observable(false);
            self.actionText = ko.computed(function () {
                return (self.active() ? gettext("Remove") : gettext("Add"));
            });
            self.toggleStatus = function () {
                self.active(!self.active());
            };
            self.error = ko.observable();
            self.requestUrl = function () {
                if (self.active()) {
                    return initialPageData.reverse('deactivate_release_restriction', self.id);
                }
                return initialPageData.reverse('activate_release_restriction', self.id);
            };
            self.toggleRestriction = function () {
                self.ajaxInProgress(true);
                var oldStatus = self.active();
                $.ajax({
                    method: 'POST',
                    url: self.requestUrl(),
                    success: function (data) {
                        if (data.success) {
                            self.toggleStatus();
                            self.activatedOn(data.activated_on);
                            self.deactivatedOn(data.deactivated_on);
                            self.error(false);
                        } else {
                            self.active(oldStatus);
                            self.errorMessage(data.message);
                        }
                    },
                    error: function () {
                        self.active(oldStatus);
                    },
                    complete: function () {
                        self.ajaxInProgress(false);
                        if (self.active() === oldStatus) {
                            self.error(true);
                        }
                    },
                });
            };
            return self;
        };

        function manageReleasesViewModel(enabledAppReleases) {
            var self = {};
            self.enabledAppReleases = ko.observableArray(enabledAppReleases);
            return self;
        }
        var enabledAppReleases = _.map(initialPageData.get('enabled_app_releases'), enabledAppRelease);
        var viewModel = manageReleasesViewModel(enabledAppReleases);
        if (enabledAppReleases.length) {
            $('#managed-releases').koApplyBindings(viewModel);
        }
        function manageReleaseSearchViewModel() {
            var self = {};
            self.appIdSearchValue = ko.observable();
            self.locationIdSearchValue = ko.observable();
            self.versionSearchValue = ko.observable();
            self.search = function () {
                window.location.search = ("location_id=" + self.locationIdSearchValue + "&app_id=" +
                    self.appIdSearchValue + "&version=" + self.versionSearchValue);
            };
            self.clear = function () {
                window.location.search = "";
            };
            return self;
        }
        var searchViewModel = manageReleaseSearchViewModel();
        $("#manage-app-releases").koApplyBindings(searchViewModel);
    });
});