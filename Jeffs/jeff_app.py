import copy
import json
import os
import uuid as uuid_lib
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_file, url_for

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['UPLOAD_FOLDER'] = 'data'

# Ensure data folder exists
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)


@app.route('/')
def index():
    """List all JSON files in the data folder."""
    json_files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.endswith('.json')]
    return render_template('index.html', files=json_files)


@app.route('/new', methods=['GET', 'POST'])
def new_group():
    """Create a new group."""
    if request.method == 'POST':
        group_data = {
            'name': request.form.get('name', 'New Group'),
            'uuid': str(uuid_lib.uuid4()),
            'lastUpdated': datetime.now().isoformat(),
            'formationBonus': request.form.get('formationBonus', ''),
            'groupLabel': request.form.get('groupLabel', ''),
            'members': [],
        }

        filename = request.form.get('filename', f'group_{group_data["uuid"][:8]}.json')
        if not filename.endswith('.json'):
            filename += '.json'

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(filepath, 'w') as f:
            json.dump(group_data, f, indent=2)

        flash(f'Group "{group_data["name"]}" created successfully!', 'success')
        return redirect(url_for('edit_group', filename=filename))

    return render_template('new_group.html')


@app.route('/edit/<filename>', methods=['GET', 'POST'])
def edit_group(filename):
    """Edit an existing group."""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        flash(f'File "{filename}" not found!', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # Update group metadata
            with open(filepath, 'r') as f:
                group_data = json.load(f)

            group_data['name'] = request.form.get('name', group_data.get('name'))
            group_data['formationBonus'] = request.form.get('formationBonus', '')
            group_data['groupLabel'] = request.form.get('groupLabel', '')
            group_data['lastUpdated'] = datetime.now().isoformat()

            with open(filepath, 'w') as f:
                json.dump(group_data, f, indent=2)

            flash('Group updated successfully!', 'success')
            return redirect(url_for('edit_group', filename=filename))
        except Exception as e:
            flash(f'Error updating group: {str(e)}', 'danger')

    with open(filepath, 'r') as f:
        group_data = json.load(f)

    return render_template('edit_group.html', group=group_data, filename=filename)


@app.route('/member/<filename>/new', methods=['GET', 'POST'])
def new_member(filename):
    """Add a new member to a group."""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        flash(f'File "{filename}" not found!', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            with open(filepath, 'r') as f:
                group_data = json.load(f)

            # Quick path: duplicate an existing member immediately
            duplicate_uuid = request.form.get('duplicate_uuid')
            if duplicate_uuid:
                src = next((m for m in group_data.get('members', []) if m.get('uuid') == duplicate_uuid), None)
                if not src:
                    flash('Selected member to duplicate was not found.', 'danger')
                    return redirect(url_for('new_member', filename=filename))

                new_member_obj = copy.deepcopy(src)
                new_member_obj['uuid'] = str(uuid_lib.uuid4())
                # Optionally mark as copy to distinguish in list
                if new_member_obj.get('name'):
                    new_member_obj['name'] = f'{new_member_obj["name"]} (Copy)'

                group_data['members'].append(new_member_obj)
                group_data['lastUpdated'] = datetime.now().isoformat()

                with open(filepath, 'w') as wf:
                    json.dump(group_data, wf, indent=2)

                flash('Member duplicated and added successfully!', 'success')
                return redirect(url_for('edit_group', filename=filename))

            member = {
                'uuid': str(uuid_lib.uuid4()),
                'class': request.form.get('class', ''),
                'variant': request.form.get('variant', ''),
                'name': request.form.get('name', ''),
                'customName': request.form.get('customName', ''),
                'classification': request.form.get('classification', ''),
                'dateIntroduced': request.form.get('dateIntroduced', ''),
                'tmm': float(request.form.get('tmm', 0) or 0),
                'tonnage': float(request.form.get('tonnage', 0) or 0),
                'tro': request.form.get('tro', ''),
                'role': request.form.get('role', ''),
                'threshold': int(request.form.get('threshold', 0) or 0),
                'costCR': float(request.form.get('costCR', 0) or 0),
                'mulID': int(request.form.get('mulID', 0) or 0),
                'basePoints': int(request.form.get('basePoints', 0) or 0),
                'currentSkill': int(request.form.get('currentSkill', 4) or 4),
                'overheat': int(request.form.get('overheat', 0) or 0),
                'structure': int(request.form.get('structure', 0) or 0),
                'armor': int(request.form.get('armor', 0) or 0),
                'type': request.form.get('type', ''),
                'size': int(request.form.get('size', 1) or 1),
                'showDetails': request.form.get('showDetails') == 'on',
                'imageURL': request.form.get('imageURL', ''),
                'currentHeat': int(request.form.get('currentHeat', 0) or 0),
                'roundHeat': int(request.form.get('roundHeat', 0) or 0),
                'abilities': [a.strip() for a in request.form.get('abilities', '').split(',') if a.strip()],
                'jumpMove': int(request.form.get('jumpMove', 0) or 0),
                'move': [
                    {
                        'move': int(request.form.get('move_value', 0) or 0),
                        'currentMove': int(request.form.get('move_current', 0) or 0),
                        'type': request.form.get('move_type', 'Walk'),
                    }
                ]
                if request.form.get('move_value')
                else [],
                'damage': {
                    'short': int(request.form.get('damage_short', 0) or 0),
                    'medium': int(request.form.get('damage_medium', 0) or 0),
                    'long': int(request.form.get('damage_long', 0) or 0),
                    'extreme': int(request.form.get('damage_extreme', 0) or 0),
                },
                'pilot': {
                    'name': request.form.get('pilot_name', ''),
                    'piloting': int(request.form.get('pilot_piloting', 4) or 4),
                    'gunnery': int(request.form.get('pilot_gunnery', 4) or 4),
                    'wounds': int(request.form.get('pilot_wounds', 0) or 0),
                },
            }

            group_data['members'].append(member)
            group_data['lastUpdated'] = datetime.now().isoformat()

            with open(filepath, 'w') as f:
                json.dump(group_data, f, indent=2)

            flash(f'Member "{member["name"]}" added successfully!', 'success')
            return redirect(url_for('edit_group', filename=filename))
        except Exception as e:
            flash(f'Error adding member: {str(e)}', 'danger')
    # GET: load group members and optional duplicate prefill
    with open(filepath, 'r') as f:
        group_data = json.load(f)

    prefill = {}
    dup_uuid = request.args.get('duplicate')
    if dup_uuid:
        src = next((m for m in group_data.get('members', []) if m.get('uuid') == dup_uuid), None)
        if src:
            # Build prefill mapping for the form fields
            move0 = (src.get('move') or [{}])[0]
            prefill = {
                'class': src.get('class', ''),
                'variant': src.get('variant', ''),
                'name': src.get('name', ''),
                'customName': src.get('customName', ''),
                'classification': src.get('classification', ''),
                'type': src.get('type', ''),
                'role': src.get('role', ''),
                'tonnage': src.get('tonnage', 0),
                'tmm': src.get('tmm', 0),
                'armor': src.get('armor', 0),
                'structure': src.get('structure', 0),
                'size': src.get('size', 1),
                'threshold': src.get('threshold', 0),
                'basePoints': src.get('basePoints', 0),
                'costCR': src.get('costCR', 0),
                'currentSkill': src.get('currentSkill', 4),
                'currentHeat': src.get('currentHeat', 0),
                'overheat': src.get('overheat', 0),
                'damage_short': (src.get('damage') or {}).get('short', 0),
                'damage_medium': (src.get('damage') or {}).get('medium', 0),
                'damage_long': (src.get('damage') or {}).get('long', 0),
                'damage_extreme': (src.get('damage') or {}).get('extreme', 0),
                'pilot_name': (src.get('pilot') or {}).get('name', ''),
                'pilot_gunnery': (src.get('pilot') or {}).get('gunnery', 4),
                'pilot_piloting': (src.get('pilot') or {}).get('piloting', 4),
                'pilot_wounds': (src.get('pilot') or {}).get('wounds', 0),
                'dateIntroduced': src.get('dateIntroduced', ''),
                'tro': src.get('tro', ''),
                'mulID': src.get('mulID', 0),
                'imageURL': src.get('imageURL', ''),
                'abilities': ', '.join(src.get('abilities', [])),
                'move_value': move0.get('move', 0),
                'move_current': move0.get('currentMove', 0),
                'move_type': move0.get('type', 'Walk'),
                'jumpMove': src.get('jumpMove', 0),
            }

    return render_template(
        'new_member.html',
        filename=filename,
        members=group_data.get('members', []),
        prefill=prefill,
    )


@app.route('/member/<filename>/edit/<member_uuid>', methods=['GET', 'POST'])
def edit_member(filename, member_uuid):
    """Edit an existing member."""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        flash(f'File "{filename}" not found!', 'danger')
        return redirect(url_for('index'))

    with open(filepath, 'r') as f:
        group_data = json.load(f)

    member = next((m for m in group_data['members'] if m['uuid'] == member_uuid), None)
    if not member:
        flash('Member not found!', 'danger')
        return redirect(url_for('edit_group', filename=filename))

    if request.method == 'POST':
        try:
            member['class'] = request.form.get('class', '')
            member['variant'] = request.form.get('variant', '')
            member['name'] = request.form.get('name', '')
            member['customName'] = request.form.get('customName', '')
            member['classification'] = request.form.get('classification', '')
            member['dateIntroduced'] = request.form.get('dateIntroduced', '')
            member['tmm'] = float(request.form.get('tmm', 0) or 0)
            member['tonnage'] = float(request.form.get('tonnage', 0) or 0)
            member['tro'] = request.form.get('tro', '')
            member['role'] = request.form.get('role', '')
            member['threshold'] = int(request.form.get('threshold', 0) or 0)
            member['costCR'] = float(request.form.get('costCR', 0) or 0)
            member['mulID'] = int(request.form.get('mulID', 0) or 0)
            member['basePoints'] = int(request.form.get('basePoints', 0) or 0)
            member['currentSkill'] = int(request.form.get('currentSkill', 4) or 4)
            member['overheat'] = int(request.form.get('overheat', 0) or 0)
            member['structure'] = int(request.form.get('structure', 0) or 0)
            member['armor'] = int(request.form.get('armor', 0) or 0)
            member['type'] = request.form.get('type', '')
            member['size'] = int(request.form.get('size', 1) or 1)
            member['showDetails'] = request.form.get('showDetails') == 'on'
            member['imageURL'] = request.form.get('imageURL', '')
            member['currentHeat'] = int(request.form.get('currentHeat', 0) or 0)
            member['roundHeat'] = int(request.form.get('roundHeat', 0) or 0)
            member['abilities'] = [a.strip() for a in request.form.get('abilities', '').split(',') if a.strip()]
            member['jumpMove'] = int(request.form.get('jumpMove', 0) or 0)
            member['move'] = (
                [
                    {
                        'move': int(request.form.get('move_value', 0) or 0),
                        'currentMove': int(request.form.get('move_current', 0) or 0),
                        'type': request.form.get('move_type', 'Walk'),
                    }
                ]
                if request.form.get('move_value')
                else member.get('move', [])
            )

            member['damage']['short'] = int(request.form.get('damage_short', 0) or 0)
            member['damage']['medium'] = int(request.form.get('damage_medium', 0) or 0)
            member['damage']['long'] = int(request.form.get('damage_long', 0) or 0)
            member['damage']['extreme'] = int(request.form.get('damage_extreme', 0) or 0)

            member['pilot']['name'] = request.form.get('pilot_name', '')
            member['pilot']['piloting'] = int(request.form.get('pilot_piloting', 4) or 4)
            member['pilot']['gunnery'] = int(request.form.get('pilot_gunnery', 4) or 4)
            member['pilot']['wounds'] = int(request.form.get('pilot_wounds', 0) or 0)

            group_data['lastUpdated'] = datetime.now().isoformat()

            with open(filepath, 'w') as f:
                json.dump(group_data, f, indent=2)

            flash('Member updated successfully!', 'success')
            return redirect(url_for('edit_group', filename=filename))
        except Exception as e:
            flash(f'Error updating member: {str(e)}', 'danger')

    return render_template('edit_member.html', member=member, filename=filename)


@app.route('/member/<filename>/delete/<member_uuid>', methods=['POST'])
def delete_member(filename, member_uuid):
    """Delete a member from a group."""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        flash(f'File "{filename}" not found!', 'danger')
        return redirect(url_for('index'))

    try:
        with open(filepath, 'r') as f:
            group_data = json.load(f)

        group_data['members'] = [m for m in group_data['members'] if m['uuid'] != member_uuid]
        group_data['lastUpdated'] = datetime.now().isoformat()

        with open(filepath, 'w') as f:
            json.dump(group_data, f, indent=2)

        flash('Member deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting member: {str(e)}', 'danger')

    return redirect(url_for('edit_group', filename=filename))


@app.route('/delete/<filename>', methods=['POST'])
def delete_group(filename):
    """Delete a group file."""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f'File "{filename}" deleted successfully!', 'success')
    else:
        flash(f'File "{filename}" not found!', 'danger')

    return redirect(url_for('index'))


@app.route('/copy/<filename>', methods=['GET', 'POST'])
def copy_group(filename):
    """Copy a group file."""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        flash(f'File "{filename}" not found!', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_filename = request.form.get('new_filename', '')
        if not new_filename:
            flash('Please provide a new filename!', 'danger')
            return render_template('copy_group.html', filename=filename)

        if not new_filename.endswith('.json'):
            new_filename += '.json'

        new_filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)

        if os.path.exists(new_filepath):
            flash(f'File "{new_filename}" already exists!', 'danger')
            return render_template('copy_group.html', filename=filename)

        try:
            with open(filepath, 'r') as f:
                group_data = json.load(f)

            # Update UUID and timestamp for the copy
            group_data['uuid'] = str(uuid_lib.uuid4())
            group_data['lastUpdated'] = datetime.now().isoformat()

            # Update member UUIDs if requested
            if request.form.get('update_member_uuids') == 'on':
                for member in group_data.get('members', []):
                    member['uuid'] = str(uuid_lib.uuid4())

            with open(new_filepath, 'w') as f:
                json.dump(group_data, f, indent=2)

            flash(f'File copied to "{new_filename}" successfully!', 'success')
            return redirect(url_for('edit_group', filename=new_filename))
        except Exception as e:
            flash(f'Error copying file: {str(e)}', 'danger')

    return render_template('copy_group.html', filename=filename)


@app.route('/rename/<filename>', methods=['GET', 'POST'])
def rename_group(filename):
    """Rename a group file."""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        flash(f'File "{filename}" not found!', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_filename = request.form.get('new_filename', '')
        if not new_filename:
            flash('Please provide a new filename!', 'danger')
            return render_template('rename_group.html', filename=filename)

        if not new_filename.endswith('.json'):
            new_filename += '.json'

        new_filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)

        if os.path.exists(new_filepath) and new_filename != filename:
            flash(f'File "{new_filename}" already exists!', 'danger')
            return render_template('rename_group.html', filename=filename)

        try:
            os.rename(filepath, new_filepath)
            flash(f'File renamed to "{new_filename}" successfully!', 'success')
            return redirect(url_for('edit_group', filename=new_filename))
        except Exception as e:
            flash(f'Error renaming file: {str(e)}', 'danger')

    return render_template('rename_group.html', filename=filename)


@app.route('/download/<filename>')
def download_file(filename):
    """Download a JSON file."""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        flash(f'File "{filename}" not found!', 'danger')
        return redirect(url_for('index'))

    # Convert to absolute path
    absolute_path = os.path.abspath(filepath)

    return send_file(absolute_path, as_attachment=True, download_name=filename, mimetype='application/json')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload a JSON file."""
    if 'file' not in request.files:
        flash('No file provided!', 'danger')
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected!', 'danger')
        return redirect(url_for('index'))

    if file and file.filename.endswith('.json'):
        try:
            # Validate JSON
            content = file.read()
            json.loads(content)

            # Save file
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            with open(filepath, 'wb') as f:
                f.write(content)

            flash(f'File "{file.filename}" uploaded successfully!', 'success')
        except json.JSONDecodeError:
            flash('Invalid JSON file!', 'danger')
        except Exception as e:
            flash(f'Error uploading file: {str(e)}', 'danger')
    else:
        flash('Only JSON files are allowed!', 'danger')

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
