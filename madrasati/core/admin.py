from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import AcademicYear, Level, School, SchoolClass, Subject


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date", "is_current"]
    list_filter = ["is_current"]


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ["name", "name_ar", "programme", "city", "class_count",
                    "is_active"]
    list_filter = ["programme", "is_active"]
    search_fields = ["name", "name_ar"]

    @admin.display(description=_("classes"))
    def class_count(self, obj):
        return obj.classes.count()


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ["code", "name_fr", "name_ar", "cycle", "order"]
    list_filter = ["cycle"]
    search_fields = ["code", "name_fr", "name_ar"]
    ordering = ["order"]


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ["__str__", "school", "level", "academic_year",
                    "main_teacher", "capacity", "student_count"]
    list_filter = ["school", "academic_year", "level__cycle", "level"]
    search_fields = ["name", "level__code"]
    autocomplete_fields = ["main_teacher"]

    @admin.display(description=_("effectif"))
    def student_count(self, obj):
        return obj.student_count


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["name_fr", "name_ar", "coefficient"]
    search_fields = ["name_fr", "name_ar"]
