-- TransferDB  CMPE 321 Project 2
-- Triggers and Stored Procedures
USE TransferDB;

-- Session variable used to bypass triggers when loading initial data.
-- SET @BYPASS_TRIGGERS = 1  before bulk inserts, then reset to 0.

DROP TRIGGER IF EXISTS trg_match_schedule_check;
DROP TRIGGER IF EXISTS trg_match_result_check;
DROP TRIGGER IF EXISTS trg_match_datetime_update;
DROP TRIGGER IF EXISTS trg_contract_insert;
DROP TRIGGER IF EXISTS trg_contract_update;
DROP TRIGGER IF EXISTS trg_squad_insert;
DROP TRIGGER IF EXISTS trg_squad_update;
DROP TRIGGER IF EXISTS trg_stats_insert;
DROP TRIGGER IF EXISTS trg_stats_update;
DROP TRIGGER IF EXISTS trg_manager_unique_club;
DROP TRIGGER IF EXISTS trg_stadium_capacity_update;
DROP PROCEDURE IF EXISTS sp_register_transfer;
DROP PROCEDURE IF EXISTS sp_submit_match_result;
DROP PROCEDURE IF EXISTS sp_finalize_squad;

DELIMITER $$

-- 120-minute conflict check on INSERT
CREATE TRIGGER trg_match_schedule_check
BEFORE INSERT ON `Match`
FOR EACH ROW
BEGIN
    IF IFNULL(@BYPASS_TRIGGERS, 0) = 0 THEN

        IF NEW.match_datetime <= NOW() THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Match must be scheduled for a future time.';
        END IF;

        IF EXISTS (
            SELECT 1 FROM `Match` M
            WHERE M.stadium_id = NEW.stadium_id
              AND ABS(TIMESTAMPDIFF(MINUTE, M.match_datetime, NEW.match_datetime)) < 120
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Stadium conflict: another match is scheduled within 120 minutes at this stadium.';
        END IF;

        IF EXISTS (
            SELECT 1 FROM `Match` M
            WHERE (M.home_club_id = NEW.home_club_id OR M.away_club_id = NEW.home_club_id)
              AND ABS(TIMESTAMPDIFF(MINUTE, M.match_datetime, NEW.match_datetime)) < 120
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Club conflict: home club already has a match within 120 minutes.';
        END IF;

        IF EXISTS (
            SELECT 1 FROM `Match` M
            WHERE (M.home_club_id = NEW.away_club_id OR M.away_club_id = NEW.away_club_id)
              AND ABS(TIMESTAMPDIFF(MINUTE, M.match_datetime, NEW.match_datetime)) < 120
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Club conflict: away club already has a match within 120 minutes.';
        END IF;

        IF EXISTS (
            SELECT 1 FROM `Match` M
            WHERE M.referee_id = NEW.referee_id
              AND ABS(TIMESTAMPDIFF(MINUTE, M.match_datetime, NEW.match_datetime)) < 120
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Referee conflict: referee already assigned to a match within 120 minutes.';
        END IF;

    END IF;
END$$

-- 120-minute conflict check on UPDATE (if datetime is changed)
CREATE TRIGGER trg_match_datetime_update
BEFORE UPDATE ON `Match`
FOR EACH ROW
BEGIN
    IF NEW.match_datetime <> OLD.match_datetime THEN

        IF EXISTS (
            SELECT 1 FROM `Match` M
            WHERE M.stadium_id = NEW.stadium_id AND M.match_id <> NEW.match_id
              AND ABS(TIMESTAMPDIFF(MINUTE, M.match_datetime, NEW.match_datetime)) < 120
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Stadium conflict: another match is scheduled within 120 minutes at this stadium.';
        END IF;

        IF EXISTS (
            SELECT 1 FROM `Match` M
            WHERE M.match_id <> NEW.match_id
              AND (M.home_club_id = NEW.home_club_id OR M.away_club_id = NEW.home_club_id)
              AND ABS(TIMESTAMPDIFF(MINUTE, M.match_datetime, NEW.match_datetime)) < 120
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Club conflict: home club has another match within 120 minutes.';
        END IF;

        IF EXISTS (
            SELECT 1 FROM `Match` M
            WHERE M.match_id <> NEW.match_id
              AND (M.home_club_id = NEW.away_club_id OR M.away_club_id = NEW.away_club_id)
              AND ABS(TIMESTAMPDIFF(MINUTE, M.match_datetime, NEW.match_datetime)) < 120
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Club conflict: away club has another match within 120 minutes.';
        END IF;

        IF EXISTS (
            SELECT 1 FROM `Match` M
            WHERE M.referee_id = NEW.referee_id AND M.match_id <> NEW.match_id
              AND ABS(TIMESTAMPDIFF(MINUTE, M.match_datetime, NEW.match_datetime)) < 120
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Referee conflict: referee has another match within 120 minutes.';
        END IF;

    END IF;
END$$

-- Result submission: match must have occurred, attendance cannot exceed capacity
CREATE TRIGGER trg_match_result_check
BEFORE UPDATE ON `Match`
FOR EACH ROW
BEGIN
    IF (NEW.home_goals IS NOT NULL OR NEW.away_goals IS NOT NULL OR NEW.attendance IS NOT NULL) THEN
        IF OLD.match_datetime > NOW() THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Match results cannot be submitted before the match has taken place.';
        END IF;
    END IF;

    IF NEW.attendance IS NOT NULL THEN
        IF NEW.attendance > (SELECT capacity FROM Stadium WHERE stadium_id = NEW.stadium_id) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Attendance exceeds the stadium capacity.';
        END IF;
    END IF;
END$$

-- Contract insert: max 1 active Permanent, max 1 active Loan, Loan requires Permanent elsewhere
CREATE TRIGGER trg_contract_insert
BEFORE INSERT ON Contract
FOR EACH ROW
BEGIN
    IF IFNULL(@BYPASS_TRIGGERS, 0) = 0 THEN

        IF NEW.contract_type = 'Permanent' THEN
            IF EXISTS (
                SELECT 1 FROM Contract C
                WHERE C.player_id = NEW.player_id
                  AND C.contract_type = 'Permanent'
                  AND C.start_date < NEW.end_date
                  AND C.end_date   > NEW.start_date
            ) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Player already has an active Permanent contract.';
            END IF;
        END IF;

        IF NEW.contract_type = 'Loan' THEN
            IF EXISTS (
                SELECT 1 FROM Contract C
                WHERE C.player_id = NEW.player_id
                  AND C.contract_type = 'Loan'
                  AND C.start_date < NEW.end_date
                  AND C.end_date   > NEW.start_date
            ) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Player already has an active Loan contract.';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM Contract C
                WHERE C.player_id = NEW.player_id
                  AND C.contract_type = 'Permanent'
                  AND C.club_id  <> NEW.club_id
                  AND C.start_date < NEW.end_date
                  AND C.end_date   > NEW.start_date
            ) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Loan contract requires an active Permanent contract with a different club.';
            END IF;
        END IF;

    END IF;
END$$

-- Contract update: prevent date changes that create overlapping active contracts
CREATE TRIGGER trg_contract_update
BEFORE UPDATE ON Contract
FOR EACH ROW
BEGIN
    IF NEW.start_date <> OLD.start_date OR NEW.end_date <> OLD.end_date THEN

        IF NEW.contract_type = 'Permanent' THEN
            IF EXISTS (
                SELECT 1 FROM Contract C
                WHERE C.player_id = NEW.player_id
                  AND C.contract_type = 'Permanent'
                  AND C.contract_id <> NEW.contract_id
                  AND C.start_date < NEW.end_date
                  AND C.end_date   > NEW.start_date
            ) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Update would create overlapping Permanent contracts.';
            END IF;
        END IF;

        IF NEW.contract_type = 'Loan' THEN
            IF EXISTS (
                SELECT 1 FROM Contract C
                WHERE C.player_id = NEW.player_id
                  AND C.contract_type = 'Loan'
                  AND C.contract_id <> NEW.contract_id
                  AND C.start_date < NEW.end_date
                  AND C.end_date   > NEW.start_date
            ) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Update would create overlapping Loan contracts.';
            END IF;
        END IF;

    END IF;
END$$

-- Squad insert: max 11 starters, max 23 total, active contract, loan parent club check
CREATE TRIGGER trg_squad_insert
BEFORE INSERT ON Match_Squad
FOR EACH ROW
BEGIN
    DECLARE v_match_date DATE;

    IF IFNULL(@BYPASS_TRIGGERS, 0) = 0 THEN

        SELECT DATE(match_datetime) INTO v_match_date
        FROM `Match` WHERE match_id = NEW.match_id;

        IF NEW.is_starter = TRUE THEN
            IF (
                SELECT COUNT(*) FROM Match_Squad MS
                WHERE MS.match_id  = NEW.match_id
                  AND MS.club_id   = NEW.club_id
                  AND MS.is_starter = TRUE
            ) >= 11 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'A club cannot have more than 11 starters in a match.';
            END IF;
        END IF;

        IF (
            SELECT COUNT(*) FROM Match_Squad MS
            WHERE MS.match_id = NEW.match_id
              AND MS.club_id  = NEW.club_id
        ) >= 23 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'A club cannot register more than 23 players per match.';
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM Contract C
            WHERE C.player_id  = NEW.player_id
              AND C.club_id    = NEW.club_id
              AND C.start_date <= v_match_date
              AND C.end_date   >  v_match_date
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Player does not have an active contract with this club on match date.';
        END IF;

        IF EXISTS (
            SELECT 1 FROM Contract C_loan
            WHERE C_loan.player_id     = NEW.player_id
              AND C_loan.contract_type  = 'Loan'
              AND C_loan.start_date    <= v_match_date
              AND C_loan.end_date      >  v_match_date
        ) THEN
            IF EXISTS (
                SELECT 1 FROM Contract C_perm
                WHERE C_perm.player_id     = NEW.player_id
                  AND C_perm.contract_type  = 'Permanent'
                  AND C_perm.club_id        = NEW.club_id
                  AND C_perm.start_date    <= v_match_date
                  AND C_perm.end_date      >  v_match_date
            ) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'A player on loan cannot participate in matches for their parent club.';
            END IF;
        END IF;

    END IF;
END$$

-- Squad update: prevent bypassing the 11-starter limit via UPDATE
CREATE TRIGGER trg_squad_update
BEFORE UPDATE ON Match_Squad
FOR EACH ROW
BEGIN
    IF NEW.is_starter = TRUE AND OLD.is_starter = FALSE THEN
        IF (
            SELECT COUNT(*) FROM Match_Squad MS
            WHERE MS.match_id  = NEW.match_id
              AND MS.club_id   = NEW.club_id
              AND MS.is_starter = TRUE
              AND MS.player_id <> NEW.player_id
        ) >= 11 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'A club cannot have more than 11 starters in a match.';
        END IF;
    END IF;
END$$

-- Stats insert: match must have occurred, max 11 starters, 2 yellows auto-sets red
CREATE TRIGGER trg_stats_insert
BEFORE INSERT ON Match_Stats
FOR EACH ROW
BEGIN
    DECLARE v_match_dt DATETIME;

    IF IFNULL(@BYPASS_TRIGGERS, 0) = 0 THEN

        SELECT match_datetime INTO v_match_dt FROM `Match` WHERE match_id = NEW.match_id;

        IF v_match_dt > NOW() THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Cannot submit player stats for a match that has not occurred yet.';
        END IF;

        IF NEW.is_starter = TRUE THEN
            IF (
                SELECT COUNT(*) FROM Match_Stats MS
                WHERE MS.match_id  = NEW.match_id
                  AND MS.club_id   = NEW.club_id
                  AND MS.is_starter = TRUE
                  AND MS.player_id <> NEW.player_id
            ) >= 11 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'A club cannot have more than 11 starters in a match.';
            END IF;
        END IF;

        IF NEW.yellow_cards = 2 THEN
            SET NEW.red_cards = TRUE;
        END IF;

    END IF;
END$$

-- Stats update: prevent bypassing the 11-starter limit via UPDATE, 2 yellows auto-sets red
CREATE TRIGGER trg_stats_update
BEFORE UPDATE ON Match_Stats
FOR EACH ROW
BEGIN
    IF NEW.is_starter = TRUE AND OLD.is_starter = FALSE THEN
        IF (
            SELECT COUNT(*) FROM Match_Stats MS
            WHERE MS.match_id  = NEW.match_id
              AND MS.club_id   = NEW.club_id
              AND MS.is_starter = TRUE
              AND MS.player_id <> NEW.player_id
        ) >= 11 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'A club cannot have more than 11 starters in a match.';
        END IF;
    END IF;

    IF NEW.yellow_cards = 2 THEN
        SET NEW.red_cards = TRUE;
    END IF;
END$$

-- Manager uniqueness on Club UPDATE
CREATE TRIGGER trg_manager_unique_club
BEFORE UPDATE ON Club
FOR EACH ROW
BEGIN
    IF NEW.manager_id IS NOT NULL AND (OLD.manager_id IS NULL OR NEW.manager_id <> OLD.manager_id) THEN
        IF EXISTS (
            SELECT 1 FROM Club C
            WHERE C.manager_id = NEW.manager_id
              AND C.club_id   <> NEW.club_id
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'This manager is already assigned to another club.';
        END IF;
    END IF;
END$$

-- Stadium capacity update: cannot set capacity below existing attendance records
CREATE TRIGGER trg_stadium_capacity_update
BEFORE UPDATE ON Stadium
FOR EACH ROW
BEGIN
    IF NEW.capacity < OLD.capacity THEN
        IF EXISTS (
            SELECT 1 FROM `Match` M
            WHERE M.stadium_id = NEW.stadium_id
              AND M.attendance > NEW.capacity
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'New capacity is less than the recorded attendance of an existing match at this stadium.';
        END IF;
    END IF;
END$$

-- Transfer registration with automatic Permanent contract termination
CREATE PROCEDURE sp_register_transfer(
    IN p_player_id    INT,
    IN p_to_club_id   INT,
    IN p_contract_type VARCHAR(20),
    IN p_weekly_wage  DECIMAL(12,2),
    IN p_transfer_fee DECIMAL(15,2),
    IN p_end_date     DATE,
    IN p_transfer_type VARCHAR(20),
    OUT p_message     VARCHAR(200)
)
BEGIN
    DECLARE v_from_club_id INT DEFAULT NULL;
    DECLARE v_today DATE DEFAULT CURDATE();
    DECLARE v_new_contract_id INT;
    DECLARE v_new_transfer_id INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        GET DIAGNOSTICS CONDITION 1 p_message = MESSAGE_TEXT;
    END;

    START TRANSACTION;

    SELECT club_id INTO v_from_club_id
    FROM Contract
    WHERE player_id    = p_player_id
      AND contract_type = 'Permanent'
      AND start_date   <= v_today
      AND end_date     >  v_today
    LIMIT 1;

    IF p_contract_type = 'Permanent' AND v_from_club_id IS NOT NULL THEN
        UPDATE Contract
        SET end_date = v_today
        WHERE player_id    = p_player_id
          AND contract_type = 'Permanent'
          AND start_date   <= v_today
          AND end_date     >  v_today;

        IF p_transfer_type = 'Purchase' THEN
            UPDATE Player
            SET market_value = p_transfer_fee
            WHERE person_id = p_player_id;
        END IF;
    END IF;

    SELECT IFNULL(MAX(contract_id), 0) + 1 INTO v_new_contract_id FROM Contract;

    INSERT INTO Contract (contract_id, player_id, club_id, start_date, end_date, weekly_wage, contract_type)
    VALUES (v_new_contract_id, p_player_id, p_to_club_id, v_today, p_end_date, p_weekly_wage, p_contract_type);

    SELECT IFNULL(MAX(transfer_id), 0) + 1 INTO v_new_transfer_id FROM Transfer_Record;

    INSERT INTO Transfer_Record (transfer_id, player_id, from_club_id, to_club_id, transfer_date, transfer_fee, transfer_type)
    VALUES (v_new_transfer_id, p_player_id, v_from_club_id, p_to_club_id, v_today, p_transfer_fee, p_transfer_type);

    COMMIT;
    SET p_message = 'OK';
END$$

-- Match result submission with referee authorization check
CREATE PROCEDURE sp_submit_match_result(
    IN p_referee_id INT,
    IN p_match_id   INT,
    IN p_home_goals INT,
    IN p_away_goals INT,
    IN p_attendance INT,
    OUT p_message   VARCHAR(200)
)
BEGIN
    DECLARE v_assigned_referee INT DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        GET DIAGNOSTICS CONDITION 1 p_message = MESSAGE_TEXT;
    END;

    START TRANSACTION;

    SELECT referee_id INTO v_assigned_referee FROM `Match` WHERE match_id = p_match_id;

    IF v_assigned_referee IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Match not found.';
    END IF;

    IF v_assigned_referee <> p_referee_id THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Only the assigned referee can submit match results.';
    END IF;

    UPDATE `Match`
    SET home_goals = p_home_goals, away_goals = p_away_goals, attendance = p_attendance
    WHERE match_id = p_match_id;

    COMMIT;
    SET p_message = 'OK';
END$$

-- Squad finalization: enforce minimum 11 players at DB level
CREATE PROCEDURE sp_finalize_squad(
    IN p_match_id INT,
    IN p_club_id  INT,
    OUT p_message VARCHAR(200)
)
BEGIN
    DECLARE v_total INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        GET DIAGNOSTICS CONDITION 1 p_message = MESSAGE_TEXT;
    END;

    SELECT COUNT(*) INTO v_total
    FROM Match_Squad
    WHERE match_id = p_match_id AND club_id = p_club_id;

    IF v_total < 11 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Squad must have at least 11 players.';
    END IF;

    SET p_message = 'OK';
END$$

DELIMITER ;
