import datetime

from django import template
from django.utils.safestring import mark_safe

from projects.models import Build


register = template.Library()


@register.simple_tag
def result(value):
    if value == Build.RESULT_PENDING:
        return mark_safe('<i class="fa fa-2x fa-question-circle-o pending" aria-hidden="true"></i>')
    elif value == Build.RESULT_FAIL:
        return mark_safe('<i class="fa fa-2x fa-exclamation-circle fail" aria-hidden="true"></i>')
    elif value == Build.RESULT_QUALIFIED_PASS:
        return mark_safe('<i class="fa fa-2x fa-check-circle-o qualified-pass" aria-hidden="true"></i>')
    elif value == Build.RESULT_PASS:
        return mark_safe('<i class="fa fa-2x fa-check-circle pass" aria-hidden="true"></i>')
    else:
        return mark_safe('<i class="fa fa-2x fa-question-circle fail" aria-hidden="true"></i>')
