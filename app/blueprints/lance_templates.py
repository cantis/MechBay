from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..services import lance_template_service

bp = Blueprint("lance_templates", __name__, url_prefix="/lance-templates")


@bp.route("")
def list_templates():
    """List all lance templates."""
    templates = lance_template_service.get_all_templates()
    return render_template("lance_templates/list.html", templates=templates)


@bp.route("/create", methods=["GET", "POST"])
def create():
    """Create a new lance template."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None

        # Get chassis patterns from form
        chassis_patterns = []
        for key in request.form:
            if key.startswith("chassis_"):
                pattern = request.form.get(key, "").strip()
                if pattern:
                    chassis_patterns.append(pattern)

        if not name:
            flash("Template name is required", "danger")
            return redirect(url_for("lance_templates.create"))

        if not chassis_patterns:
            flash("At least one chassis pattern is required", "danger")
            return redirect(url_for("lance_templates.create"))

        lance_template_service.create_template(name, chassis_patterns, description)
        flash(f"Template '{name}' created successfully", "success")
        return redirect(url_for("lance_templates.list_templates"))

    return render_template("lance_templates/create.html")


@bp.route("/<int:id>")
def detail(id: int):  # noqa: A002
    """View template details."""
    template = lance_template_service.get_template_details(id)
    if not template:
        flash("Template not found", "danger")
        return redirect(url_for("lance_templates.list_templates"))

    return render_template("lance_templates/detail.html", template=template)


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
def edit(id: int):  # noqa: A002
    """Edit a lance template."""
    template = lance_template_service.get_template_details(id)
    if not template:
        flash("Template not found", "danger")
        return redirect(url_for("lance_templates.list_templates"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None

        # Get chassis patterns from form
        chassis_patterns = []
        for key in request.form:
            if key.startswith("chassis_"):
                pattern = request.form.get(key, "").strip()
                if pattern:
                    chassis_patterns.append(pattern)

        if not name:
            flash("Template name is required", "danger")
            return redirect(url_for("lance_templates.edit", id=id))

        if not chassis_patterns:
            flash("At least one chassis pattern is required", "danger")
            return redirect(url_for("lance_templates.edit", id=id))

        lance_template_service.update_template(id, name, chassis_patterns, description)
        flash(f"Template '{name}' updated successfully", "success")
        return redirect(url_for("lance_templates.detail", id=id))

    return render_template("lance_templates/edit.html", template=template)


@bp.route("/<int:id>/delete", methods=["POST"])
def delete(id: int):  # noqa: A002
    """Delete a lance template."""
    success = lance_template_service.delete_template(id)
    if success:
        flash("Template deleted", "info")
    else:
        flash("Template not found", "danger")

    return redirect(url_for("lance_templates.list_templates"))
