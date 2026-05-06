
import re
from functools import wraps
from datetime import date

import bcrypt
from flask import (Flask, render_template, request, session,
                   redirect, url_for, flash)

from config import SECRET_KEY
from db import get_connection, query, callproc
import datetime

app = Flask(__name__)
app.secret_key = SECRET_KEY


@app.context_processor
def inject_globals():
    today = datetime.date.today()
    return dict(today=today, now_date=today, enumerate=enumerate)


# Helpers

def validate_password(pw: str):
    if len(pw) < 8:
        return False, 'Password must be at least 8 characters.'
    if not re.search(r'[A-Z]', pw):
        return False, 'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]', pw):
        return False, 'Password must contain at least one lowercase letter.'
    if not re.search(r'[0-9]', pw):
        return False, 'Password must contain at least one digit.'
    if not re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>?/\\|`~]', pw):
        return False, 'Password must contain at least one special character.'
    return True, ''


def login_required(roles=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user' not in session:
                flash('Please log in first.', 'warning')
                return redirect(url_for('login'))
            if roles and session.get('role') not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# Root / Dashboard

@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'user' in session else url_for('login'))


@app.route('/dashboard')
def dashboard():
    role = session.get('role')
    if not role:
        return redirect(url_for('login'))
    return redirect(url_for(f'{role}_dashboard'))


# Login

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Try DB Manager
        row, _ = query(
            "SELECT username, password_hash FROM DatabaseManager WHERE username = %s",
            (username,), fetchone=True)
        if row and bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
            session['user'] = username
            session['role'] = 'db_manager'
            return redirect(url_for('db_manager_dashboard'))

        # Try Person subtypes
        row, _ = query(
            "SELECT P.person_id, P.username, P.password_hash, "
            "  CASE WHEN PL.person_id IS NOT NULL THEN 'player' "
            "       WHEN M.person_id  IS NOT NULL THEN 'manager' "
            "       WHEN R.person_id  IS NOT NULL THEN 'referee' END AS role "
            "FROM Person P "
            "LEFT JOIN Player  PL ON PL.person_id = P.person_id "
            "LEFT JOIN Manager M  ON M.person_id  = P.person_id "
            "LEFT JOIN Referee R  ON R.person_id  = P.person_id "
            "WHERE P.username = %s",
            (username,), fetchone=True)

        if row and row['role'] and bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
            session['user']      = username
            session['person_id'] = row['person_id']
            session['role']      = row['role']
            return redirect(url_for('dashboard'))

        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


# Signup

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        role     = request.form.get('role', '')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        ok, msg = validate_password(password)
        if not ok:
            flash(msg, 'danger')
            return render_template('signup.html')

        # Check username uniqueness across all tables
        if role == 'db_manager':
            exists, _ = query("SELECT 1 FROM DatabaseManager WHERE username = %s",
                              (username,), fetchone=True)
        else:
            exists, _ = query("SELECT 1 FROM Person WHERE username = %s",
                              (username,), fetchone=True)
        if exists:
            flash('Username already taken.', 'danger')
            return render_template('signup.html')

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        if role == 'db_manager':
            _, err = query(
                "INSERT INTO DatabaseManager (username, password_hash) VALUES (%s,%s)",
                (username, pw_hash), commit=True)
            if err:
                flash(f'Error: {err}', 'danger')
                return render_template('signup.html')
            flash('DB Manager account created. Please log in.', 'success')
            return redirect(url_for('login'))

        # Get next person_id
        row, _ = query("SELECT IFNULL(MAX(person_id),0)+1 AS nid FROM Person", fetchone=True)
        new_pid = row['nid']

        name        = request.form.get('name', '').strip()
        surname     = request.form.get('surname', '').strip()
        nationality = request.form.get('nationality', '').strip()
        dob         = request.form.get('date_of_birth', '').strip()

        _, err = query(
            "INSERT INTO Person (person_id, username, password_hash, name, surname, nationality, date_of_birth) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (new_pid, username, pw_hash, name, surname, nationality, dob), commit=True)
        if err:
            flash(f'Error: {err}', 'danger')
            return render_template('signup.html')

        if role == 'player':
            mv    = request.form.get('market_value', 0)
            pos   = request.form.get('main_position', '')
            foot  = request.form.get('strong_foot', '')
            ht    = request.form.get('height', 0)
            _, err = query(
                "INSERT INTO Player (person_id, market_value, main_position, strong_foot, height) "
                "VALUES (%s,%s,%s,%s,%s)",
                (new_pid, mv, pos, foot, ht), commit=True)

        elif role == 'manager':
            formation = request.form.get('preferred_formation', '').strip()
            exp_level = request.form.get('experience_level', '')
            _, err = query(
                "INSERT INTO Manager (person_id, preferred_formation, experience_level) "
                "VALUES (%s,%s,%s)",
                (new_pid, formation, exp_level), commit=True)

        elif role == 'referee':
            lic = request.form.get('license_level', '')
            yoe = request.form.get('years_of_experience', 0)
            _, err = query(
                "INSERT INTO Referee (person_id, license_level, years_of_experience) "
                "VALUES (%s,%s,%s)",
                (new_pid, lic, yoe), commit=True)

        if err:
            flash(f'Error: {err}', 'danger')
        else:
            flash('Account created successfully. Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))


# --- Database Manager Routes ---

@app.route('/db_manager/dashboard')
@login_required(roles=['db_manager'])
def db_manager_dashboard():
    return render_template('db_manager/dashboard.html')


# Op 2: View Stadiums

@app.route('/db_manager/stadiums')
@login_required(roles=['db_manager'])
def view_stadiums():
    rows, err = query(
        "SELECT S.stadium_id, S.stadium_name, S.city, S.capacity, "
        "       GROUP_CONCAT(C.club_name SEPARATOR ', ') AS home_clubs "
        "FROM Stadium S "
        "LEFT JOIN Club C ON C.stadium_id = S.stadium_id "
        "GROUP BY S.stadium_id, S.stadium_name, S.city, S.capacity "
        "ORDER BY S.city, S.stadium_name",
        fetchall=True)
    return render_template('db_manager/stadiums.html', stadiums=rows, err=err)


# Op 3: Schedule a Match

@app.route('/db_manager/schedule_match', methods=['GET', 'POST'])
@login_required(roles=['db_manager'])
def schedule_match():
    if request.method == 'POST':
        match_date  = request.form.get('match_date', '')
        match_time  = request.form.get('match_time', '')
        stadium_id  = request.form.get('stadium_id', '')
        home_id     = request.form.get('home_club_id', '')
        away_id     = request.form.get('away_club_id', '')
        referee_id  = request.form.get('referee_id', '')
        comp_id     = request.form.get('competition_id', '')
        match_dt    = f'{match_date} {match_time}:00'

        # Get next match_id
        row, _ = query("SELECT IFNULL(MAX(match_id),0)+1 AS nid FROM `Match`", fetchone=True)
        new_mid = row['nid']

        _, err = query(
            "INSERT INTO `Match` "
            "(match_id, competition_id, home_club_id, away_club_id, stadium_id, referee_id, match_datetime) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (new_mid, comp_id, home_id, away_id, stadium_id, referee_id, match_dt),
            commit=True)

        if err:
            # Strip MySQL error code prefix for cleaner UX
            msg = re.sub(r'^\d+\s+\(.*?\):\s*', '', err)
            flash(f'Error: {msg}', 'danger')
        else:
            flash('Match scheduled successfully.', 'success')

    clubs, _    = query("SELECT club_id, club_name FROM Club ORDER BY club_name", fetchall=True)
    stadiums, _ = query("SELECT stadium_id, stadium_name, city FROM Stadium ORDER BY stadium_name", fetchall=True)
    refs, _     = query(
        "SELECT R.person_id, P.name, P.surname, R.license_level "
        "FROM Referee R JOIN Person P ON P.person_id = R.person_id "
        "ORDER BY P.surname", fetchall=True)
    comps, _    = query(
        "SELECT competition_id, name, season FROM Competition ORDER BY season DESC, name",
        fetchall=True)
    return render_template('db_manager/schedule_match.html',
                           clubs=clubs, stadiums=stadiums, refs=refs, comps=comps)


# Op 9: Register Transfer & Contract

@app.route('/db_manager/register_transfer', methods=['GET', 'POST'])
@login_required(roles=['db_manager'])
def register_transfer():
    if request.method == 'POST':
        player_id     = request.form.get('player_id', '')
        to_club_id    = request.form.get('to_club_id', '')
        contract_type = request.form.get('contract_type', '')
        weekly_wage   = request.form.get('weekly_wage', '0')
        transfer_fee  = request.form.get('transfer_fee', '0')
        end_date      = request.form.get('end_date', '')
        transfer_type = request.form.get('transfer_type', '')

        out_msg = ''
        _, err = callproc('sp_register_transfer',
                          (player_id, to_club_id, contract_type,
                           float(weekly_wage), float(transfer_fee),
                           end_date, transfer_type, out_msg))
        if err:
            msg = re.sub(r'^\d+\s+\(.*?\):\s*', '', str(err))
            flash(f'Error: {msg}', 'danger')
        else:
            flash('Transfer and contract registered successfully.', 'success')

    players, _ = query(
        "SELECT P.person_id, P.name, P.surname, PL.market_value "
        "FROM Player PL JOIN Person P ON P.person_id = PL.person_id "
        "ORDER BY P.surname", fetchall=True)
    clubs, _ = query("SELECT club_id, club_name FROM Club ORDER BY club_name", fetchall=True)
    return render_template('db_manager/register_transfer.html', players=players, clubs=clubs)


# Op 10: Rename Stadium

@app.route('/db_manager/rename_stadium', methods=['GET', 'POST'])
@login_required(roles=['db_manager'])
def rename_stadium():
    if request.method == 'POST':
        stadium_id = request.form.get('stadium_id', '')
        new_name   = request.form.get('new_name', '').strip()
        _, err = query(
            "UPDATE Stadium SET stadium_name = %s WHERE stadium_id = %s",
            (new_name, stadium_id), commit=True)
        if err:
            flash(f'Error: {err}', 'danger')
        else:
            flash('Stadium renamed successfully.', 'success')

    stadiums, _ = query(
        "SELECT stadium_id, stadium_name, city FROM Stadium ORDER BY stadium_name",
        fetchall=True)
    return render_template('db_manager/rename_stadium.html', stadiums=stadiums)


# Op 11: Assign Manager to Club

@app.route('/db_manager/assign_manager', methods=['GET', 'POST'])
@login_required(roles=['db_manager'])
def assign_manager():
    if request.method == 'POST':
        club_id    = request.form.get('club_id', '')
        manager_id = request.form.get('manager_id', '') or None

        # Unassign manager from any other club first
        if manager_id:
            _, err = query(
                "UPDATE Club SET manager_id = NULL WHERE manager_id = %s",
                (manager_id,), commit=True)

        _, err = query(
            "UPDATE Club SET manager_id = %s WHERE club_id = %s",
            (manager_id, club_id), commit=True)

        if err:
            msg = re.sub(r'^\d+\s+\(.*?\):\s*', '', str(err))
            flash(f'Error: {msg}', 'danger')
        else:
            flash('Manager assignment updated.', 'success')

    clubs, _ = query(
        "SELECT C.club_id, C.club_name, "
        "       P.name AS mgr_name, P.surname AS mgr_surname "
        "FROM Club C "
        "LEFT JOIN Manager M  ON M.person_id  = C.manager_id "
        "LEFT JOIN Person  P  ON P.person_id  = C.manager_id "
        "ORDER BY C.club_name", fetchall=True)
    managers, _ = query(
        "SELECT M.person_id, P.name, P.surname "
        "FROM Manager M JOIN Person P ON P.person_id = M.person_id "
        "ORDER BY P.surname", fetchall=True)
    return render_template('db_manager/assign_manager.html', clubs=clubs, managers=managers)


# Op 12: Create Competition

@app.route('/db_manager/create_competition', methods=['GET', 'POST'])
@login_required(roles=['db_manager'])
def create_competition():
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        season  = request.form.get('season', '').strip()
        country = request.form.get('country', '').strip()
        ctype   = request.form.get('competition_type', '')

        row, _ = query(
            "SELECT IFNULL(MAX(competition_id),0)+1 AS nid FROM Competition", fetchone=True)
        new_cid = row['nid']

        _, err = query(
            "INSERT INTO Competition (competition_id, name, season, country, competition_type) "
            "VALUES (%s,%s,%s,%s,%s)",
            (new_cid, name, season, country, ctype), commit=True)

        if err:
            msg = re.sub(r'^\d+\s+\(.*?\):\s*', '', str(err))
            flash(f'Error: {msg}', 'danger')
        else:
            flash('Competition created successfully.', 'success')

    comps, _ = query(
        "SELECT name, season, country, competition_type FROM Competition "
        "ORDER BY season DESC, name", fetchall=True)
    return render_template('db_manager/create_competition.html', comps=comps)


# DB Manager: Create User

@app.route('/db_manager/create_user', methods=['GET', 'POST'])
@login_required(roles=['db_manager'])
def create_user():
    """DB Manager can create players, managers, referees, and other DB managers."""
    return redirect(url_for('signup'))


# --- Player Routes ---

@app.route('/player/dashboard')
@login_required(roles=['player'])
def player_dashboard():
    pid = session['person_id']
    row, _ = query(
        "SELECT P.name, P.surname, P.nationality, P.date_of_birth, "
        "       PL.market_value, PL.main_position, PL.strong_foot, PL.height, "
        "       C.club_name AS current_club "
        "FROM Person P "
        "JOIN Player PL ON PL.person_id = P.person_id "
        "LEFT JOIN Contract CT ON CT.player_id = P.person_id "
        "    AND CT.start_date <= CURDATE() AND CT.end_date > CURDATE() "
        "    AND CT.contract_type = 'Permanent' "
        "LEFT JOIN Club C ON C.club_id = CT.club_id "
        "WHERE P.person_id = %s",
        (pid,), fetchone=True)
    return render_template('player/dashboard.html', profile=row)


# Op 16: Performance Statistics

@app.route('/player/stats')
@login_required(roles=['player'])
def player_stats():
    pid     = session['person_id']
    season  = request.args.get('season', '').strip()
    comp_id = request.args.get('competition_id', '').strip()

    base = (
        "SELECT COUNT(DISTINCT MS.match_id) AS games_played, "
        "       SUM(MS.goals)         AS goals, "
        "       SUM(MS.assists)       AS assists, "
        "       SUM(MS.yellow_cards)  AS yellow_cards, "
        "       SUM(MS.red_cards)     AS red_cards, "
        "       ROUND(AVG(MS.rating),2) AS avg_rating "
        "FROM Match_Stats MS "
        "JOIN `Match` M ON M.match_id = MS.match_id "
        "JOIN Competition C ON C.competition_id = M.competition_id "
        "WHERE MS.player_id = %s"
    )
    params = [pid]
    if season:
        base += " AND C.season = %s"
        params.append(season)
    if comp_id:
        base += " AND C.competition_id = %s"
        params.append(comp_id)

    stats, _ = query(base, tuple(params), fetchone=True)

    seasons, _ = query(
        "SELECT DISTINCT C.season FROM Competition C "
        "JOIN `Match` M ON M.competition_id = C.competition_id "
        "JOIN Match_Stats MS ON MS.match_id = M.match_id "
        "WHERE MS.player_id = %s ORDER BY C.season DESC",
        (pid,), fetchall=True)
    comps, _ = query(
        "SELECT DISTINCT C.competition_id, C.name, C.season "
        "FROM Competition C "
        "JOIN `Match` M ON M.competition_id = C.competition_id "
        "JOIN Match_Stats MS ON MS.match_id = M.match_id "
        "WHERE MS.player_id = %s ORDER BY C.season DESC, C.name",
        (pid,), fetchall=True)

    return render_template('player/stats.html',
                           stats=stats, seasons=seasons, comps=comps,
                           sel_season=season, sel_comp=comp_id)


# Op 17: Match History

@app.route('/player/match_history')
@login_required(roles=['player'])
def player_match_history():
    pid = session['person_id']
    rows, _ = query(
        "SELECT M.match_datetime, C.name AS competition, S.stadium_name, "
        "       HC.club_name AS home_club, AC.club_name AS away_club, "
        "       M.home_goals, M.away_goals, "
        "       MS.club_id, MS.minutes_played, MS.position_in_match, "
        "       MS.goals, MS.assists, MS.yellow_cards, MS.red_cards, MS.rating, "
        "       MS.is_starter "
        "FROM Match_Stats MS "
        "JOIN `Match` M      ON M.match_id       = MS.match_id "
        "JOIN Competition C   ON C.competition_id = M.competition_id "
        "JOIN Stadium S       ON S.stadium_id     = M.stadium_id "
        "JOIN Club HC         ON HC.club_id       = M.home_club_id "
        "JOIN Club AC         ON AC.club_id       = M.away_club_id "
        "WHERE MS.player_id = %s "
        "ORDER BY M.match_datetime DESC",
        (pid,), fetchall=True)

    return render_template('player/match_history.html', matches=rows)


# Op 18: Career History

@app.route('/player/career_history')
@login_required(roles=['player'])
def player_career_history():
    pid = session['person_id']
    contracts, _ = query(
        "SELECT C.club_name, CT.contract_type, CT.weekly_wage, "
        "       CT.start_date, CT.end_date "
        "FROM Contract CT "
        "JOIN Club C ON C.club_id = CT.club_id "
        "WHERE CT.player_id = %s "
        "ORDER BY CT.start_date DESC",
        (pid,), fetchall=True)

    transfers, _ = query(
        "SELECT TR.transfer_date, TR.transfer_fee, TR.transfer_type, "
        "       FC.club_name AS from_club, TC.club_name AS to_club "
        "FROM Transfer_Record TR "
        "LEFT JOIN Club FC ON FC.club_id = TR.from_club_id "
        "JOIN Club TC      ON TC.club_id = TR.to_club_id "
        "WHERE TR.player_id = %s "
        "ORDER BY TR.transfer_date DESC",
        (pid,), fetchall=True)

    return render_template('player/career_history.html',
                           contracts=contracts, transfers=transfers)


# --- Manager Routes ---

def get_manager_club(person_id):
    """Return the club_id assigned to this manager, or None."""
    row, _ = query(
        "SELECT club_id, club_name FROM Club WHERE manager_id = %s",
        (person_id,), fetchone=True)
    return row


@app.route('/manager/dashboard')
@login_required(roles=['manager'])
def manager_dashboard():
    pid = session['person_id']
    row, _ = query(
        "SELECT P.name, P.surname, P.nationality, P.date_of_birth, "
        "       M.preferred_formation, M.experience_level, "
        "       C.club_name AS current_club "
        "FROM Person P "
        "JOIN Manager M ON M.person_id = P.person_id "
        "LEFT JOIN Club C ON C.manager_id = P.person_id "
        "WHERE P.person_id = %s",
        (pid,), fetchone=True)
    return render_template('manager/dashboard.html', profile=row)


# Op 4: Fixtures & Results

@app.route('/manager/fixtures')
@login_required(roles=['manager'])
def manager_fixtures():
    pid   = session['person_id']
    club  = get_manager_club(pid)
    if not club:
        flash('You are not assigned to a club.', 'warning')
        return render_template('manager/fixtures.html', matches=[], club=None,
                               competitions=[], sel_comp='', sel_season='')

    cid       = club['club_id']
    sel_comp  = request.args.get('competition_id', '').strip()
    sel_season = request.args.get('season', '').strip()

    sql = (
        "SELECT M.match_id, M.match_datetime, "
        "       COMP.name AS competition, COMP.season, "
        "       S.stadium_name, "
        "       HC.club_name AS home_club, AC.club_name AS away_club, "
        "       M.home_goals, M.away_goals "
        "FROM `Match` M "
        "JOIN Competition COMP ON COMP.competition_id = M.competition_id "
        "JOIN Stadium S        ON S.stadium_id        = M.stadium_id "
        "JOIN Club HC          ON HC.club_id          = M.home_club_id "
        "JOIN Club AC          ON AC.club_id          = M.away_club_id "
        "WHERE (M.home_club_id = %s OR M.away_club_id = %s) "
    )
    params = [cid, cid]
    if sel_comp:
        sql += " AND M.competition_id = %s "
        params.append(sel_comp)
    if sel_season:
        sql += " AND COMP.season = %s "
        params.append(sel_season)
    sql += " ORDER BY M.match_datetime DESC"

    matches, _ = query(sql, tuple(params), fetchall=True)

    # Derive result for each completed match
    enriched = []
    for m in matches:
        m = dict(m)
        if m['home_goals'] is not None:
            is_home = (m['home_club'] == club['club_name'])
            my_goals = m['home_goals'] if is_home else m['away_goals']
            opp_goals = m['away_goals'] if is_home else m['home_goals']
            if my_goals > opp_goals:
                m['result'] = 'Win'
            elif my_goals < opp_goals:
                m['result'] = 'Loss'
            else:
                m['result'] = 'Draw'
        else:
            m['result'] = 'Scheduled'
        enriched.append(m)

    comps, _ = query(
        "SELECT DISTINCT COMP.competition_id, COMP.name, COMP.season "
        "FROM Competition COMP "
        "JOIN `Match` M ON M.competition_id = COMP.competition_id "
        "WHERE M.home_club_id = %s OR M.away_club_id = %s "
        "ORDER BY COMP.season DESC, COMP.name",
        (cid, cid), fetchall=True)

    return render_template('manager/fixtures.html',
                           matches=enriched, club=club,
                           competitions=comps,
                           sel_comp=sel_comp, sel_season=sel_season)


# Op 5: Submit Match Squad

@app.route('/manager/squad_submit/<int:match_id>', methods=['GET', 'POST'])
@login_required(roles=['manager'])
def squad_submit(match_id):
    pid  = session['person_id']
    club = get_manager_club(pid)
    if not club:
        flash('You are not assigned to a club.', 'warning')
        return redirect(url_for('manager_fixtures'))

    cid = club['club_id']

    if request.method == 'POST':
        selected_players = request.form.getlist('player_ids')
        starters         = request.form.getlist('starter_ids')

        if len(selected_players) < 11 or len(selected_players) > 23:
            flash('Squad must have between 11 and 23 players.', 'danger')
        elif len(starters) > 11:
            flash('Maximum 11 starters allowed.', 'danger')
        else:
            # Clear existing squad for this club in this match
            _, _ = query(
                "DELETE FROM Match_Squad WHERE match_id = %s AND club_id = %s",
                (match_id, cid), commit=True)

            errors = []
            for p in selected_players:
                is_starter = (p in starters)
                _, err = query(
                    "INSERT INTO Match_Squad (player_id, match_id, club_id, is_starter) "
                    "VALUES (%s,%s,%s,%s)",
                    (p, match_id, cid, is_starter), commit=True)
                if err:
                    errors.append(re.sub(r'^\d+\s+\(.*?\):\s*', '', str(err)))

            if errors:
                for e in errors:
                    flash(f'Error: {e}', 'danger')
            else:
                _, fin_err = callproc('sp_finalize_squad', (match_id, cid, ''))
                if fin_err:
                    msg = re.sub(r'^\d+\s+\(.*?\):\s*', '', str(fin_err))
                    flash(f'Error: {msg}', 'danger')
                else:
                    flash('Squad submitted successfully.', 'success')
                    return redirect(url_for('manager_fixtures'))

    # Active roster: players with active contract with this club on match date
    match_row, _ = query(
        "SELECT match_datetime FROM `Match` WHERE match_id = %s", (match_id,), fetchone=True)
    if not match_row:
        flash('Match not found.', 'danger')
        return redirect(url_for('manager_fixtures'))

    match_date = match_row['match_datetime'].date() if hasattr(match_row['match_datetime'], 'date') else match_row['match_datetime']

    players, _ = query(
        "SELECT P.person_id, P.name, P.surname, PL.main_position "
        "FROM Player PL "
        "JOIN Person P ON P.person_id = PL.person_id "
        "JOIN Contract CT ON CT.player_id = PL.person_id "
        "WHERE CT.club_id = %s "
        "  AND CT.start_date <= %s AND CT.end_date > %s "
        "  AND NOT EXISTS ( "
        "      SELECT 1 FROM Contract CL "
        "      WHERE CL.player_id = PL.person_id "
        "        AND CL.contract_type = 'Loan' "
        "        AND CL.start_date <= %s AND CL.end_date > %s "
        "        AND (SELECT C2.club_id FROM Contract C2 "
        "             WHERE C2.player_id = PL.person_id "
        "               AND C2.contract_type = 'Permanent' "
        "               AND C2.start_date <= %s AND C2.end_date > %s LIMIT 1) = %s "
        "  ) "
        "GROUP BY P.person_id, P.name, P.surname, PL.main_position "
        "ORDER BY P.surname",
        (cid, match_date, match_date,
         match_date, match_date,
         match_date, match_date, cid),
        fetchall=True)

    current_squad, _ = query(
        "SELECT player_id, is_starter FROM Match_Squad "
        "WHERE match_id = %s AND club_id = %s",
        (match_id, cid), fetchall=True)
    current_ids   = {r['player_id'] for r in (current_squad or [])}
    current_starters = {r['player_id'] for r in (current_squad or []) if r['is_starter']}

    return render_template('manager/squad_submit.html',
                           players=players, match_id=match_id,
                           current_ids=current_ids,
                           current_starters=current_starters,
                           match_date=match_date)


# Op 6: League Standings

@app.route('/manager/standings')
@login_required(roles=['manager'])
def manager_standings():
    pid  = session['person_id']
    club = get_manager_club(pid)

    comp_id    = request.args.get('competition_id', '').strip()
    sel_season = request.args.get('season', '').strip()

    standings = []
    if comp_id and sel_season:
        standings, _ = query(
            "SELECT C.club_name, "
            "       COUNT(M.match_id)   AS played, "
            "       SUM(CASE WHEN (M.home_club_id = C.club_id AND M.home_goals > M.away_goals) "
            "                  OR (M.away_club_id = C.club_id AND M.away_goals > M.home_goals) "
            "                THEN 1 ELSE 0 END) AS wins, "
            "       SUM(CASE WHEN M.home_goals = M.away_goals THEN 1 ELSE 0 END) AS draws, "
            "       SUM(CASE WHEN (M.home_club_id = C.club_id AND M.home_goals < M.away_goals) "
            "                  OR (M.away_club_id = C.club_id AND M.away_goals < M.home_goals) "
            "                THEN 1 ELSE 0 END) AS losses, "
            "       SUM(CASE WHEN M.home_club_id = C.club_id THEN M.home_goals ELSE M.away_goals END) AS gf, "
            "       SUM(CASE WHEN M.home_club_id = C.club_id THEN M.away_goals ELSE M.home_goals END) AS ga, "
            "       SUM(CASE WHEN M.home_club_id = C.club_id THEN M.home_goals ELSE M.away_goals END) "
            "     - SUM(CASE WHEN M.home_club_id = C.club_id THEN M.away_goals ELSE M.home_goals END) AS gd, "
            "       SUM(CASE WHEN (M.home_club_id = C.club_id AND M.home_goals > M.away_goals) "
            "                  OR (M.away_club_id = C.club_id AND M.away_goals > M.home_goals) "
            "                THEN 3 "
            "                WHEN M.home_goals = M.away_goals THEN 1 ELSE 0 END) AS pts "
            "FROM Club C "
            "JOIN `Match` M ON (M.home_club_id = C.club_id OR M.away_club_id = C.club_id) "
            "JOIN Competition COMP ON COMP.competition_id = M.competition_id "
            "WHERE M.competition_id = %s AND COMP.season = %s "
            "  AND M.home_goals IS NOT NULL "
            "GROUP BY C.club_id, C.club_name "
            "ORDER BY pts DESC, gd DESC",
            (comp_id, sel_season), fetchall=True)

    # Competitions the manager's club has been in
    comps = []
    if club:
        comps, _ = query(
            "SELECT DISTINCT COMP.competition_id, COMP.name, COMP.season "
            "FROM Competition COMP "
            "JOIN `Match` M ON M.competition_id = COMP.competition_id "
            "WHERE (M.home_club_id = %s OR M.away_club_id = %s) "
            "  AND COMP.competition_type = 'League' "
            "ORDER BY COMP.season DESC, COMP.name",
            (club['club_id'], club['club_id']), fetchall=True)

    return render_template('manager/standings.html',
                           standings=standings, comps=comps,
                           sel_comp=comp_id, sel_season=sel_season)


# Op 7: Squad Statistics

@app.route('/manager/squad_stats')
@login_required(roles=['manager'])
def manager_squad_stats():
    pid  = session['person_id']
    club = get_manager_club(pid)
    if not club:
        flash('You are not assigned to a club.', 'warning')
        return render_template('manager/squad_stats.html', players=[], club=None,
                               comps=[], sel_comp='', sel_season='')

    cid        = club['club_id']
    sel_comp   = request.args.get('competition_id', '').strip()
    sel_season = request.args.get('season', '').strip()

    if sel_comp and sel_season:
        # Historical: players who played for this club in that competition+season
        players, _ = query(
            "SELECT P.name, P.surname, PL.main_position, PL.strong_foot, PL.height, "
            "       PL.market_value, P.nationality, "
            "       TIMESTAMPDIFF(YEAR, P.date_of_birth, CURDATE()) AS age, "
            "       COUNT(DISTINCT MS.match_id)       AS played, "
            "       SUM(MS.goals)                     AS goals, "
            "       SUM(MS.assists)                   AS assists, "
            "       SUM(MS.yellow_cards)              AS yellow_cards, "
            "       SUM(MS.red_cards)                 AS red_cards, "
            "       ROUND(AVG(MS.rating),2)           AS avg_rating, "
            "       ROUND(AVG(MS.minutes_played),1)   AS avg_minutes "
            "FROM Match_Stats MS "
            "JOIN `Match` M   ON M.match_id        = MS.match_id "
            "JOIN Competition COMP ON COMP.competition_id = M.competition_id "
            "JOIN Player PL   ON PL.person_id      = MS.player_id "
            "JOIN Person P    ON P.person_id        = MS.player_id "
            "WHERE MS.club_id = %s AND M.competition_id = %s AND COMP.season = %s "
            "GROUP BY P.person_id, P.name, P.surname, PL.main_position, "
            "         PL.strong_foot, PL.height, PL.market_value, P.nationality, P.date_of_birth "
            "ORDER BY P.surname",
            (cid, sel_comp, sel_season), fetchall=True)

    elif sel_season:
        # Season filter only
        players, _ = query(
            "SELECT P.name, P.surname, PL.main_position, PL.strong_foot, PL.height, "
            "       PL.market_value, P.nationality, "
            "       TIMESTAMPDIFF(YEAR, P.date_of_birth, CURDATE()) AS age, "
            "       COUNT(DISTINCT MS.match_id)       AS played, "
            "       SUM(MS.goals)                     AS goals, "
            "       SUM(MS.assists)                   AS assists, "
            "       SUM(MS.yellow_cards)              AS yellow_cards, "
            "       SUM(MS.red_cards)                 AS red_cards, "
            "       ROUND(AVG(MS.rating),2)           AS avg_rating, "
            "       ROUND(AVG(MS.minutes_played),1)   AS avg_minutes "
            "FROM Match_Stats MS "
            "JOIN `Match` M   ON M.match_id = MS.match_id "
            "JOIN Competition COMP ON COMP.competition_id = M.competition_id "
            "JOIN Player PL ON PL.person_id = MS.player_id "
            "JOIN Person P  ON P.person_id  = MS.player_id "
            "WHERE MS.club_id = %s AND COMP.season = %s "
            "GROUP BY P.person_id, P.name, P.surname, PL.main_position, "
            "         PL.strong_foot, PL.height, PL.market_value, P.nationality, P.date_of_birth "
            "ORDER BY P.surname",
            (cid, sel_season), fetchall=True)

    else:
        # Default: current squad with all-time stats for this club
        players, _ = query(
            "SELECT P.name, P.surname, PL.main_position, PL.strong_foot, PL.height, "
            "       PL.market_value, P.nationality, "
            "       TIMESTAMPDIFF(YEAR, P.date_of_birth, CURDATE()) AS age, "
            "       COUNT(DISTINCT MS.match_id)       AS played, "
            "       SUM(MS.goals)                     AS goals, "
            "       SUM(MS.assists)                   AS assists, "
            "       SUM(MS.yellow_cards)              AS yellow_cards, "
            "       SUM(MS.red_cards)                 AS red_cards, "
            "       ROUND(AVG(MS.rating),2)           AS avg_rating, "
            "       ROUND(AVG(MS.minutes_played),1)   AS avg_minutes "
            "FROM Player PL "
            "JOIN Person P ON P.person_id = PL.person_id "
            "JOIN Contract CT ON CT.player_id = PL.person_id "
            "    AND CT.club_id = %s "
            "    AND CT.start_date <= CURDATE() AND CT.end_date > CURDATE() "
            "LEFT JOIN Match_Stats MS ON MS.player_id = PL.person_id AND MS.club_id = %s "
            "GROUP BY P.person_id, P.name, P.surname, PL.main_position, "
            "         PL.strong_foot, PL.height, PL.market_value, P.nationality, P.date_of_birth "
            "ORDER BY P.surname",
            (cid, cid), fetchall=True)

    comps, _ = query(
        "SELECT DISTINCT COMP.competition_id, COMP.name, COMP.season "
        "FROM Competition COMP "
        "JOIN `Match` M ON M.competition_id = COMP.competition_id "
        "JOIN Match_Stats MS ON MS.match_id = M.match_id "
        "WHERE MS.club_id = %s "
        "ORDER BY COMP.season DESC, COMP.name",
        (cid,), fetchall=True)

    return render_template('manager/squad_stats.html',
                           players=players, club=club,
                           comps=comps, sel_comp=sel_comp, sel_season=sel_season)


# Op 8: Competition Leaderboard

@app.route('/manager/leaderboard')
@login_required(roles=['manager'])
def manager_leaderboard():
    pid  = session['person_id']
    club = get_manager_club(pid)

    comp_id    = request.args.get('competition_id', '').strip()
    sel_season = request.args.get('season', '').strip()
    category   = request.args.get('category', 'goals')

    top_players = []
    if comp_id and sel_season:
        if category == 'goals':
            top_players, _ = query(
                "SELECT P.name, P.surname, C.club_name, "
                "       COUNT(DISTINCT MS.match_id) AS played, "
                "       SUM(MS.goals) AS metric "
                "FROM Match_Stats MS "
                "JOIN `Match` M   ON M.match_id        = MS.match_id "
                "JOIN Competition COMP ON COMP.competition_id = M.competition_id "
                "JOIN Person P    ON P.person_id        = MS.player_id "
                "JOIN Club C      ON C.club_id          = MS.club_id "
                "WHERE M.competition_id = %s AND COMP.season = %s "
                "GROUP BY MS.player_id, P.name, P.surname, C.club_name "
                "ORDER BY metric DESC LIMIT 10",
                (comp_id, sel_season), fetchall=True)

        elif category == 'assists':
            top_players, _ = query(
                "SELECT P.name, P.surname, C.club_name, "
                "       COUNT(DISTINCT MS.match_id) AS played, "
                "       SUM(MS.assists) AS metric "
                "FROM Match_Stats MS "
                "JOIN `Match` M   ON M.match_id        = MS.match_id "
                "JOIN Competition COMP ON COMP.competition_id = M.competition_id "
                "JOIN Person P    ON P.person_id        = MS.player_id "
                "JOIN Club C      ON C.club_id          = MS.club_id "
                "WHERE M.competition_id = %s AND COMP.season = %s "
                "GROUP BY MS.player_id, P.name, P.surname, C.club_name "
                "ORDER BY metric DESC LIMIT 10",
                (comp_id, sel_season), fetchall=True)

        elif category == 'rating':
            top_players, _ = query(
                "SELECT P.name, P.surname, C.club_name, "
                "       COUNT(DISTINCT MS.match_id) AS played, "
                "       ROUND(AVG(MS.rating),2) AS metric "
                "FROM Match_Stats MS "
                "JOIN `Match` M   ON M.match_id        = MS.match_id "
                "JOIN Competition COMP ON COMP.competition_id = M.competition_id "
                "JOIN Person P    ON P.person_id        = MS.player_id "
                "JOIN Club C      ON C.club_id          = MS.club_id "
                "WHERE M.competition_id = %s AND COMP.season = %s "
                "GROUP BY MS.player_id, P.name, P.surname, C.club_name "
                "HAVING played >= 3 "
                "ORDER BY metric DESC LIMIT 10",
                (comp_id, sel_season), fetchall=True)

    comps = []
    if club:
        comps, _ = query(
            "SELECT DISTINCT COMP.competition_id, COMP.name, COMP.season "
            "FROM Competition COMP "
            "JOIN `Match` M ON M.competition_id = COMP.competition_id "
            "WHERE (M.home_club_id = %s OR M.away_club_id = %s) "
            "ORDER BY COMP.season DESC, COMP.name",
            (club['club_id'], club['club_id']), fetchall=True)

    return render_template('manager/leaderboard.html',
                           top_players=top_players, comps=comps,
                           sel_comp=comp_id, sel_season=sel_season,
                           category=category)


# --- Referee Routes ---

@app.route('/referee/dashboard')
@login_required(roles=['referee'])
def referee_dashboard():
    pid = session['person_id']
    row, _ = query(
        "SELECT P.name, P.surname, P.nationality, P.date_of_birth, "
        "       R.license_level, R.years_of_experience "
        "FROM Person P "
        "JOIN Referee R ON R.person_id = P.person_id "
        "WHERE P.person_id = %s",
        (pid,), fetchone=True)
    return render_template('referee/dashboard.html', profile=row)


# Op 13: Submit Match Result

@app.route('/referee/submit_result/<int:match_id>', methods=['GET', 'POST'])
@login_required(roles=['referee'])
def submit_result(match_id):
    pid = session['person_id']

    match_row, _ = query(
        "SELECT M.match_id, M.match_datetime, M.referee_id, "
        "       M.home_goals, M.away_goals, M.attendance, "
        "       M.stadium_id, S.capacity, "
        "       HC.club_id AS home_club_id, HC.club_name AS home_club, "
        "       AC.club_id AS away_club_id, AC.club_name AS away_club, "
        "       COMP.name AS competition "
        "FROM `Match` M "
        "JOIN Stadium S ON S.stadium_id = M.stadium_id "
        "JOIN Club HC   ON HC.club_id   = M.home_club_id "
        "JOIN Club AC   ON AC.club_id   = M.away_club_id "
        "JOIN Competition COMP ON COMP.competition_id = M.competition_id "
        "WHERE M.match_id = %s",
        (match_id,), fetchone=True)

    if not match_row:
        flash('Match not found.', 'danger')
        return redirect(url_for('referee_match_history'))

    if match_row['referee_id'] != pid:
        flash('You are not the assigned referee for this match.', 'danger')
        return redirect(url_for('referee_match_history'))

    if match_row['match_datetime'] > __import__('datetime').datetime.now():
        flash('Match has not taken place yet.', 'warning')
        return redirect(url_for('referee_match_history'))

    if request.method == 'POST':
        home_goals = request.form.get('home_goals', '0')
        away_goals = request.form.get('away_goals', '0')
        attendance = request.form.get('attendance', '0')

        _, err = callproc('sp_submit_match_result',
                          (pid, match_id, int(home_goals), int(away_goals), int(attendance), ''))

        if err:
            msg = re.sub(r'^\d+\s+\(.*?\):\s*', '', str(err))
            flash(f'Error: {msg}', 'danger')
        else:
            # Insert player stats
            player_ids = request.form.getlist('player_id')
            errors = []
            for p in player_ids:
                def g(k): return request.form.get(f'{k}_{p}', '0')
                is_starter  = 1 if request.form.get(f'is_starter_{p}') else 0
                minutes     = int(g('minutes_played'))
                pos_m       = request.form.get(f'position_in_match_{p}', 'CM').strip()
                goals       = int(g('goals'))
                assists     = int(g('assists'))
                yellow      = int(g('yellow_cards'))
                red         = 1 if int(g('yellow_cards')) >= 2 or g('red_cards') == '1' else 0
                rating      = float(g('rating'))
                club_id_p   = request.form.get(f'club_id_{p}', '')

                _, err2 = query(
                    "INSERT INTO Match_Stats "
                    "(player_id, match_id, club_id, is_starter, minutes_played, "
                    " position_in_match, goals, assists, yellow_cards, red_cards, rating) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE "
                    "is_starter=VALUES(is_starter), minutes_played=VALUES(minutes_played), "
                    "position_in_match=VALUES(position_in_match), goals=VALUES(goals), "
                    "assists=VALUES(assists), yellow_cards=VALUES(yellow_cards), "
                    "red_cards=VALUES(red_cards), rating=VALUES(rating)",
                    (int(p), match_id, int(club_id_p), is_starter,
                     minutes, pos_m, goals, assists, yellow, red, rating),
                    commit=True)
                if err2:
                    errors.append(re.sub(r'^\d+\s+\(.*?\):\s*', '', str(err2)))

            if errors:
                for e in errors:
                    flash(f'Player stat error: {e}', 'danger')
            else:
                flash('Match result submitted successfully.', 'success')
                return redirect(url_for('referee_match_history'))

    # Get squad for both clubs from Match_Squad (manager-submitted) or show empty form
    squad, _ = query(
        "SELECT MS.player_id, MS.club_id, MS.is_starter, "
        "       P.name, P.surname, PL.main_position "
        "FROM Match_Squad MS "
        "JOIN Person P  ON P.person_id  = MS.player_id "
        "JOIN Player PL ON PL.person_id = MS.player_id "
        "WHERE MS.match_id = %s "
        "ORDER BY MS.club_id, MS.is_starter DESC, P.surname",
        (match_id,), fetchall=True)

    return render_template('referee/submit_result.html',
                           match=match_row, squad=squad)


# Op 14: Referee Career Stats

@app.route('/referee/career_stats')
@login_required(roles=['referee'])
def referee_career_stats():
    pid = session['person_id']
    stats, _ = query(
        "SELECT COUNT(DISTINCT M.match_id)  AS total_matches, "
        "       SUM(MS.yellow_cards)        AS total_yellow, "
        "       SUM(MS.red_cards)           AS total_red "
        "FROM `Match` M "
        "LEFT JOIN Match_Stats MS ON MS.match_id = M.match_id "
        "WHERE M.referee_id = %s AND M.home_goals IS NOT NULL",
        (pid,), fetchone=True)
    return render_template('referee/career_stats.html', stats=stats)


# Op 15: Referee Match History

@app.route('/referee/match_history')
@login_required(roles=['referee'])
def referee_match_history():
    pid = session['person_id']
    rows, _ = query(
        "SELECT M.match_id, M.match_datetime, COMP.name AS competition, "
        "       S.stadium_name, M.attendance, "
        "       M.home_goals, M.away_goals, "
        "       HC.club_name AS home_club, AC.club_name AS away_club, "
        "       SUM(MS.yellow_cards) AS yellow_total, "
        "       SUM(MS.red_cards)    AS red_total "
        "FROM `Match` M "
        "JOIN Competition COMP ON COMP.competition_id = M.competition_id "
        "JOIN Stadium S        ON S.stadium_id        = M.stadium_id "
        "JOIN Club HC          ON HC.club_id          = M.home_club_id "
        "JOIN Club AC          ON AC.club_id          = M.away_club_id "
        "LEFT JOIN Match_Stats MS ON MS.match_id      = M.match_id "
        "WHERE M.referee_id = %s "
        "GROUP BY M.match_id, M.match_datetime, COMP.name, S.stadium_name, "
        "         M.attendance, M.home_goals, M.away_goals, HC.club_name, AC.club_name "
        "ORDER BY M.match_datetime DESC",
        (pid,), fetchall=True)
    return render_template('referee/match_history.html', matches=rows)


# Entry point
if __name__ == '__main__':
    app.run(debug=True, port=5000)
