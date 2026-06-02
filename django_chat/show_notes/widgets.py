from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

import django.forms
from django import forms
from django.forms.renderers import BaseRenderer, EngineMixin
from django.template.backends.django import DjangoTemplates as DjangoTemplateBackend
from django.utils.safestring import mark_safe

from django_chat.imports.show_notes import RESOLVE_LABEL_TO_KIND, SALE_KEYWORDS


class _ProjectFormRenderer(EngineMixin, BaseRenderer):
    """Form renderer that searches both the project's template directories and
    Django's built-in widget templates.  Used exclusively by IconChoiceWidget
    so that icon_choice*.html templates are found without changing the global
    FORM_RENDERER setting (which would break Wagtail admin widget templates)."""

    backend = DjangoTemplateBackend

    @cached_property
    def engine(self):
        from django.conf import settings

        project_dirs = []
        for tpl_conf in settings.TEMPLATES:
            project_dirs.extend(tpl_conf.get("DIRS", []))

        # Django's own form widget templates (text.html, input.html, etc.)
        django_forms_templates = Path(django.forms.__file__).parent / "templates"

        return self.backend(
            {
                "APP_DIRS": True,
                "DIRS": [*project_dirs, django_forms_templates],
                "NAME": "django_chat_form_renderer",
                "OPTIONS": {},
            }
        )


_renderer = _ProjectFormRenderer()


class IconChoiceWidget(forms.RadioSelect):
    template_name = "cast/django_chat/show_notes/widgets/icon_choice.html"
    option_template_name = "cast/django_chat/show_notes/widgets/icon_choice_option.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        options = []
        for _group, group_options, _index in context["widget"]["optgroups"]:
            options.extend(group_options)
        auto_option = None
        manual_options = []
        for option in options:
            if str(option["value"]) == "auto":
                auto_option = option
            else:
                manual_options.append(option)
        context["auto_option"] = auto_option
        context["manual_options"] = manual_options
        context["manual_selected"] = any(opt["selected"] for opt in manual_options)
        context["option_template"] = self.option_template_name
        # Data for the optional JS live-preview of the auto-resolved icon. The
        # rule DATA comes from the Python constants (single source); the JS only
        # mirrors the small matcher and clones SVGs from the rendered tiles.
        context["resolve_labels_json"] = json.dumps(RESOLVE_LABEL_TO_KIND, sort_keys=True)
        context["sale_keywords_json"] = json.dumps(list(SALE_KEYWORDS))
        context["dashboard_keyword"] = "dashboard"
        return context

    def _render(self, template_name, context, renderer=None):
        return mark_safe(_renderer.render(template_name, context))

    class Media:
        css = {"all": ["django_chat/css/icon_choice_widget.css"]}
        js = ["django_chat/js/icon_choice_widget.js"]
