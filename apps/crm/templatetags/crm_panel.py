from django import template

from apps.crm.action_template_utils import org_action_donut_data

register = template.Library()


@register.simple_tag
def org_action_donut(actions):
    return org_action_donut_data(actions)
