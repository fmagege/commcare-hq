import json
import re
from corehq.apps.data_interfaces.models import (AutomaticUpdateRuleCriteria, AutomaticUpdateAction,
    MatchPropertyDefinition)
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es
from corehq.apps.style import crispy as hqcrispy
from couchdbkit import ResourceNotFound

from corehq.toggles import AUTO_CASE_UPDATE_ENHANCEMENTS
from crispy_forms.bootstrap import StrictButton, InlineField, FormActions, FieldWithButtons
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, HTML, Div, Fieldset
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from corehq.apps.casegroups.models import CommCareCaseGroup
from dimagi.utils.django.fields import TrimmedCharField


def true_or_false(value):
    if value == 'true':
        return True
    elif value == 'false':
        return False

    raise ValueError("Expected 'true' or 'false'")


def remove_quotes(value):
    if isinstance(value, basestring) and len(value) >= 2:
        for q in ("'", '"'):
            if value.startswith(q) and value.endswith(q):
                return value[1:-1]
    return value


def validate_case_property_name(value):
    if not isinstance(value, basestring):
        raise ValidationError(_("Please specify a case property name."))

    value = value.strip()
    property_name = re.sub('^(parent/)+', '', value)
    if not property_name:
        raise ValidationError(_("Please specify a case property name."))

    if '/' in property_name:
        raise ValidationError(
            _("Case property reference cannot contain '/' unless referencing the parent case with 'parent/'")
        )

    if not re.match('^[a-zA-Z0-9_-]+$', property_name):
        raise ValidationError(
            _("Property names should only contain alphanumeric characters, underscore, or hyphen.")
        )

    return value


def validate_case_property_value(value):
    if not isinstance(value, basestring):
        raise ValidationError(_("Please specify a case property value."))

    value = remove_quotes(value.strip()).strip()
    if not value:
        raise ValidationError(_("Please specify a case property value."))

    return value


def validate_non_negative_days(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(_("Please enter a number of days greater than or equal to zero"))

    if value < 0:
        raise ValidationError(_("Please enter a number of days greater than or equal to zero"))

    return value


class AddCaseGroupForm(forms.Form):
    name = forms.CharField(required=True, label=ugettext_noop("Group Name"))

    def __init__(self, *args, **kwargs):
        super(AddCaseGroupForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_style = 'inline'
        self.helper.form_show_labels = False
        self.helper.layout = Layout(
            InlineField('name'),
            StrictButton(
                mark_safe('<i class="fa fa-plus"></i> %s' % _("Create Group")),
                css_class='btn-success',
                type="submit"
            )
        )

    def create_group(self, domain):
        group = CommCareCaseGroup(
            name=self.cleaned_data['name'],
            domain=domain
        )
        group.save()
        return group


class UpdateCaseGroupForm(AddCaseGroupForm):
    item_id = forms.CharField(widget=forms.HiddenInput())
    action = forms.CharField(widget=forms.HiddenInput(), initial="update_case_group")

    def __init__(self, *args, **kwargs):
        super(UpdateCaseGroupForm, self).__init__(*args, **kwargs)

        self.fields['name'].label = ""

        self.helper.form_style = 'inline'
        self.helper.form_method = 'post'
        self.helper.form_show_labels = True
        self.helper.layout = Layout(
            'item_id',
            'action',
            FieldWithButtons(
                Field('name', placeholder="Group Name"),
                StrictButton(
                    _("Update Group Name"),
                    css_class='btn-primary',
                    type="submit",
                )
            ),
        )

    def clean(self):
        cleaned_data = super(UpdateCaseGroupForm, self).clean()
        try:
            self.current_group = CommCareCaseGroup.get(self.cleaned_data.get('item_id'))
        except AttributeError:
            raise forms.ValidationError("You're not passing in the group's id!")
        except ResourceNotFound:
            raise forms.ValidationError("This case group was not found in our database!")
        return cleaned_data

    def update_group(self):
        self.current_group.name = self.cleaned_data['name']
        self.current_group.save()
        return self.current_group


class AddCaseToGroupForm(forms.Form):
    case_identifier = forms.CharField(label=ugettext_noop("Case ID, External ID, or Phone Number"))

    def __init__(self, *args, **kwargs):
        super(AddCaseToGroupForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_style = 'inline'
        self.helper.form_show_labels = False
        self.helper.layout = Layout(
            InlineField(
                'case_identifier'
            ),
            StrictButton(
                mark_safe('<i class="fa fa-plus"></i> %s' % _("Add Case")),
                css_class='btn-success',
                type="submit"
            )
        )


class AddAutomaticCaseUpdateRuleForm(forms.Form):
    ACTION_CLOSE = 'CLOSE'
    ACTION_UPDATE_AND_CLOSE = 'UPDATE_AND_CLOSE'
    ACTION_UPDATE = 'UPDATE'

    name = TrimmedCharField(
        label=ugettext_lazy("Rule Name"),
        required=True,
    )
    case_type = forms.ChoiceField(
        label=ugettext_lazy("Case Type"),
        required=True,
    )
    filter_on_server_modified = forms.ChoiceField(
        label=ugettext_lazy("Filter on Last Modified"),
        choices=(
            ('true', ugettext_lazy("Yes")),
            ('false', ugettext_lazy("No")),
        ),
        required=False
    )
    server_modified_boundary = forms.IntegerField(
        label=ugettext_lazy("enter number of days"),
        required=False,
    )
    conditions = forms.CharField(
        required=True,
    )
    action = forms.ChoiceField(
        label=ugettext_lazy("Set a Case Property"),
        choices=(
            (ACTION_UPDATE_AND_CLOSE,
                ugettext_lazy("Yes")),
            (ACTION_CLOSE,
                ugettext_lazy("No")),
        ),
    )
    update_property_name = TrimmedCharField(
        required=False,
    )
    property_value_type = forms.ChoiceField(
        label=ugettext_lazy('Value Type'),
        choices=AutomaticUpdateAction.PROPERTY_TYPE_CHOICES,
        required=False
    )
    update_property_value = TrimmedCharField(
        required=False,
    )

    def remove_quotes(self, value):
        if isinstance(value, basestring) and len(value) >= 2:
            for q in ("'", '"'):
                if value.startswith(q) and value.endswith(q):
                    return value[1:-1]
        return value

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            value = self[field_name].value()
            if field_name == 'conditions':
                value = value or '[]'
                value = json.loads(value)
            values[field_name] = value
        return values

    def set_case_type_choices(self, initial):
        case_types = [''] + list(get_case_types_for_domain_es(self.domain))
        if initial and initial not in case_types:
            # Include the deleted case type in the list of choices so that
            # we always allow proper display and edit of rules
            case_types.append(initial)
        case_types.sort()
        self.fields['case_type'].choices = (
            (case_type, case_type) for case_type in case_types
        )

    def allow_updates_without_closing(self):
        """
        If the AUTO_CASE_UPDATE_ENHANCEMENTS toggle is enabled for the domain, then
        we allow updates to happen without closing the case.
        """
        self.fields['action'].choices = (
            (self.ACTION_CLOSE, _("No")),
            (self.ACTION_UPDATE_AND_CLOSE, _("Yes, and close the case")),
            (self.ACTION_UPDATE, _("Yes, and do not close the case")),
        )

    def __init__(self, *args, **kwargs):
        if 'domain' not in kwargs:
            raise Exception("Expected domain in kwargs")
        self.domain = kwargs.pop('domain')
        self.enhancements_enabled = AUTO_CASE_UPDATE_ENHANCEMENTS.enabled(self.domain)
        super(AddAutomaticCaseUpdateRuleForm, self).__init__(*args, **kwargs)

        if not self.enhancements_enabled:
            # Always set the value of filter_on_server_modified to true when the
            # enhancement toggle is not set
            self.data = self.data.copy()
            self.initial['filter_on_server_modified'] = 'true'
            self.data['filter_on_server_modified'] = 'true'

        # We can't set these fields to be required because they are displayed
        # conditionally and we'll confuse django validation if we make them
        # required. However, we should show the asterisk for consistency, since
        # when they are displayed they are required.
        self.fields['update_property_name'].label = _("Property") + '<span class="asteriskField">*</span>'
        self.fields['update_property_value'].label = _("Value") + '<span class="asteriskField">*</span>'
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-4 col-md-3'
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'

        if self.enhancements_enabled:
            self.allow_updates_without_closing()

        _update_property_fields = filter(None, [
            Field(
                'update_property_name',
                ng_model='update_property_name',
                css_class='case-property-typeahead',
            ),
            Field(
                'property_value_type',
                ng_model='property_value_type',
            ) if self.enhancements_enabled else None,
            Field(
                'update_property_value',
                ng_model='update_property_value',
            )
        ])

        _basic_info_fields = filter(None, [
            Field(
                'name',
                ng_model='name',
            ),
            Field(
                'case_type',
                ng_model='case_type',
            ),
            Field(
                'filter_on_server_modified',
                ng_model='filter_on_server_modified',
            ) if self.enhancements_enabled else None,
            hqcrispy.B3MultiField(
                _("Close Case") + '<span class="asteriskField">*</span>',
                Div(
                    hqcrispy.MultiInlineField(
                        'server_modified_boundary',
                        ng_model='server_modified_boundary',
                    ),
                    css_class='col-sm-6',
                ),
                Div(
                    HTML('<label class="control-label">%s</label>' %
                         _('days after the case was last modified.')),
                    css_class='col-sm-6',
                ),
                help_bubble_text=_("This will close the case if it has been "
                                   "more than the chosen number of days since "
                                   "the case was last modified. Cases are "
                                   "checked against this rule weekly."),
                css_id='server_modified_boundary_multifield',
                label_class=self.helper.label_class,
                field_class='col-sm-8 col-md-6',
                ng_show='showServerModifiedBoundaryField()',
            ),
            Field(
                'action',
                ng_model='action',
            ),
            Div(
                *_update_property_fields,
                ng_show='showUpdateProperty()'
            )
        ])

        self.set_case_type_choices(self.initial.get('case_type'))
        self.helper.layout = Layout(
            Fieldset(
                _("Basic Information"),
                *_basic_info_fields
            ),
            Fieldset(
                _("Filter Cases to Close (Optional)"),
                Field(
                    'conditions',
                    type='hidden',
                    ng_value='conditions',
                ),
                Div(ng_include='', src="'conditions.tpl'"),
            ),
            FormActions(
                StrictButton(
                    _("Save"),
                    type='submit',
                    css_class='btn btn-primary col-sm-offset-1',
                ),
            ),
        )

    def clean_server_modified_boundary(self):
        value = self.cleaned_data.get('server_modified_boundary')

        if self.enhancements_enabled:
            if not self.cleaned_data.get('filter_on_server_modified'):
                return None

            if not isinstance(value, int) or value <= 0:
                raise ValidationError(_("Please enter a whole number greater than 0."))
        else:
            if not isinstance(value, int) or value < 30:
                raise ValidationError(_("Please enter a whole number greater than or equal to 30."))

        return value

    def _clean_case_property_name(self, value):
        if not isinstance(value, basestring):
            raise ValidationError(_("Please specify a case property name."))

        value = value.strip()
        if not value:
            raise ValidationError(_("Please specify a case property name."))

        if value.startswith('/'):
            raise ValidationError(_("Case property names cannot start with a '/'"))

        return value

    def clean_conditions(self):
        result = []
        value = self.cleaned_data.get('conditions')
        try:
            value = json.loads(value)
        except:
            raise ValidationError(_("Invalid JSON"))

        valid_match_types = [choice[0] for choice in AutomaticUpdateRuleCriteria.MATCH_TYPE_CHOICES]

        for obj in value:
            property_name = self._clean_case_property_name(obj.get('property_name'))

            property_match_type = obj.get('property_match_type')
            if property_match_type not in valid_match_types:
                raise ValidationError(_("Invalid match type given"))

            property_value = None
            if property_match_type != AutomaticUpdateRuleCriteria.MATCH_HAS_VALUE:
                property_value = obj.get('property_value')
                if not isinstance(property_value, basestring):
                    raise ValidationError(_("Please specify a property value."))

                property_value = property_value.strip()
                property_value = self.remove_quotes(property_value)
                if not property_value:
                    raise ValidationError(_("Please specify a property value."))

                if property_match_type in (
                    AutomaticUpdateRuleCriteria.MATCH_DAYS_AFTER,
                    AutomaticUpdateRuleCriteria.MATCH_DAYS_BEFORE,
                ):
                    try:
                        property_value = int(property_value)
                    except:
                        raise ValidationError(_("Please enter a number of days that is a number."))

            result.append(dict(
                property_name=property_name,
                property_match_type=property_match_type,
                property_value=property_value,
            ))
        return result

    def _closes_case(self):
        return self.cleaned_data.get('action') in [
            self.ACTION_UPDATE_AND_CLOSE,
            self.ACTION_CLOSE,
        ]

    def _updates_case(self):
        return self.cleaned_data.get('action') in [
            self.ACTION_UPDATE_AND_CLOSE,
            self.ACTION_UPDATE,
        ]

    def clean_update_property_name(self):
        if self._updates_case():
            return self._clean_case_property_name(self.cleaned_data.get('update_property_name'))

        return None

    def clean_update_property_value(self):
        value = None
        if self._updates_case():
            value = self.cleaned_data.get('update_property_value')
            value = self.remove_quotes(value)
            if not value:
                raise ValidationError(_("This field is required"))
        return value

    def clean_filter_on_server_modified(self):
        if not self.enhancements_enabled:
            return True
        else:
            string_value = self.cleaned_data.get('filter_on_server_modified')
            return json.loads(string_value)

    def clean_property_value_type(self):
        if not self.enhancements_enabled:
            return AutomaticUpdateAction.EXACT
        else:
            return self.cleaned_data.get('property_value_type')


class CaseUpdateRuleForm(forms.Form):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "rule-"
    prefix = "rule"

    name = TrimmedCharField(
        label=ugettext_lazy("Name"),
        required=True,
    )

    def __init__(self, domain, *args, **kwargs):
        super(CaseUpdateRuleForm, self).__init__(*args, **kwargs)

        self.domain = domain
        self.helper = FormHelper()
        self.helper.label_class = 'col-xs-2 col-xs-offset-1'
        self.helper.field_class = 'col-xs-2'
        self.helper.form_tag = False

        self.helper.layout = Layout(
            Fieldset(
                _("Basic Information"),
                Field('name', data_bind='name'),
            ),
        )


class CaseRuleCriteriaForm(forms.Form):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "criteria-"
    prefix = "criteria"

    case_type = forms.ChoiceField(
        label=ugettext_lazy("Case Type"),
        required=True,
    )

    filter_on_server_modified = forms.CharField(required=False)
    server_modified_boundary = forms.CharField(required=False)
    custom_match_definitions = forms.CharField(required=False)
    property_match_definitions = forms.CharField(required=False)
    filter_on_closed_parent = forms.CharField(required=False)

    @property
    def constants(self):
        return {
            'MATCH_DAYS_BEFORE': MatchPropertyDefinition.MATCH_DAYS_BEFORE,
            'MATCH_DAYS_AFTER': MatchPropertyDefinition.MATCH_DAYS_AFTER,
            'MATCH_EQUAL': MatchPropertyDefinition.MATCH_EQUAL,
            'MATCH_NOT_EQUAL': MatchPropertyDefinition.MATCH_NOT_EQUAL,
            'MATCH_HAS_VALUE': MatchPropertyDefinition.MATCH_HAS_VALUE,
        }

    def __init__(self, domain, *args, **kwargs):
        super(CaseRuleCriteriaForm, self).__init__(*args, **kwargs)

        self.domain = domain
        self.set_case_type_choices(self.initial.get('case_type'))

        self.helper = FormHelper()
        self.helper.label_class = 'col-xs-2 col-xs-offset-1'
        self.helper.field_class = 'col-xs-2'
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                _("Case Filters"),
                HTML(
                    '<p class="help-block"><i class="fa fa-info-circle"></i> %s</p>' %
                    _("The Rule Actions will be performed for cases that match all filter criteria below.")
                ),
                self._hidden_bound_field('filter_on_server_modified'),
                self._hidden_bound_field('server_modified_boundary'),
                self._hidden_bound_field('custom_match_definitions'),
                self._hidden_bound_field('property_match_definitions'),
                self._hidden_bound_field('filter_on_closed_parent'),
                Div(data_bind="template: {name: 'case-filters'}"),
                css_id="rule-criteria",
            ),
        )

        self.case_type_helper = FormHelper()
        self.case_type_helper.label_class = 'col-xs-2 col-xs-offset-1'
        self.case_type_helper.field_class = 'col-xs-2'
        self.case_type_helper.form_tag = False
        self.case_type_helper.layout = Layout(Field('case_type'))

    def _hidden_bound_field(self, field_name):
        return Field(
            field_name,
            type='hidden',
            data_bind='value: %s' % field_name,
        )

    def _json_fail_hard(self):
        raise ValueError("Invalid JSON object given")

    def set_case_type_choices(self, initial):
        case_types = [''] + list(get_case_types_for_domain_es(self.domain))
        if initial and initial not in case_types:
            # Include the deleted case type in the list of choices so that
            # we always allow proper display and edit of rules
            case_types.append(initial)
        case_types.sort()
        self.fields['case_type'].choices = (
            (case_type, case_type) for case_type in case_types
        )

    def clean_filter_on_server_modified(self):
        return true_or_false(self.cleaned_data.get('filter_on_server_modified'))

    def clean_server_modified_boundary(self):
        # Be explicit about this check to prevent any accidents in the future
        if self.cleaned_data['filter_on_server_modified'] is False:
            return None

        value = self.cleaned_data.get('server_modified_boundary')
        return validate_non_negative_days(value)

    def clean_custom_match_definitions(self):
        value = self.cleaned_data.get('custom_match_definitions')
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            self._json_fail_hard()

        if not isinstance(value, list):
            self._json_fail_hard()

        result = []

        for obj in value:
            if not isinstance(obj, dict):
                self._json_fail_hard()

            if 'name' not in obj:
                self._json_fail_hard()

            name = obj['name'].strip()
            if not name or name not in settings.AVAILABLE_CUSTOM_RULE_CRITERIA:
                raise ValidationError(_("Invalid custom callout reference"))

            result.append({
                'name': name
            })

        return result

    def clean_property_match_definitions(self):
        value = self.cleaned_data.get('property_match_definitions')
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            self._json_fail_hard()

        if not isinstance(value, list):
            self._json_fail_hard()

        result = []

        for obj in value:
            if not isinstance(obj, dict):
                self._json_fail_hard()

            if (
                'property_name' not in obj or
                'property_value' not in obj or
                'match_type' not in obj
            ):
                self._json_fail_hard()

            property_name = validate_case_property_name(obj['property_name'])
            match_type = obj['match_type']
            if match_type not in MatchPropertyDefinition.MATCH_CHOICES:
                self._json_fail_hard()

            if match_type == MatchPropertyDefinition.MATCH_HAS_VALUE:
                result.append({
                    'property_name': property_name,
                    'property_value': None,
                    'match_type': match_type,
                })
            elif match_type in (
                MatchPropertyDefinition.MATCH_EQUAL,
                MatchPropertyDefinition.MATCH_NOT_EQUAL,
            ):
                property_value = validate_case_property_value(obj['property_value'])
                result.append({
                    'property_name': property_name,
                    'property_value': property_value,
                    'match_type': match_type,
                })
            elif match_type in (
                MatchPropertyDefinition.MATCH_DAYS_BEFORE,
                MatchPropertyDefinition.MATCH_DAYS_AFTER,
            ):
                property_value = validate_case_property_value(obj['property_value'])
                try:
                    property_value = int(property_value)
                except (TypeError, ValueError):
                    raise ValidationError(_("Please enter a number of days"))

                result.append({
                    'property_name': property_name,
                    'property_value': property_value,
                    'match_type': match_type,
                })

        return result

    def clean_filter_on_closed_parent(self):
        return true_or_false(self.cleaned_data.get('filter_on_closed_parent'))
