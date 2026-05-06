-- TransferDB  CMPE 321 Project 2
-- MySQL DDL Schema

DROP DATABASE IF EXISTS TransferDB;
CREATE DATABASE TransferDB;
USE TransferDB;

-- DatabaseManager  (separate user table)
CREATE TABLE DatabaseManager (
    username     VARCHAR(50),
    password_hash VARCHAR(255) NOT NULL,
    PRIMARY KEY (username)
);

-- Person  (supertype for Player / Manager / Referee)
CREATE TABLE Person (
    person_id    INT,
    username     VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name         VARCHAR(100) NOT NULL,
    surname      VARCHAR(100) NOT NULL,
    nationality  VARCHAR(100) NOT NULL,
    date_of_birth DATE        NOT NULL,
    PRIMARY KEY (person_id)
);

-- Player  ISA Person
CREATE TABLE Player (
    person_id    INT,
    market_value DECIMAL(15,2) NOT NULL,
    main_position VARCHAR(20) NOT NULL,
    strong_foot  VARCHAR(10)  NOT NULL,
    height       INT          NOT NULL,
    PRIMARY KEY (person_id),
    FOREIGN KEY (person_id) REFERENCES Person(person_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CHECK (market_value > 0),
    CHECK (height > 0),
    CHECK (main_position IN ('Goalkeeper','Defender','Midfielder','Forward')),
    CHECK (strong_foot IN ('Right','Left','Both'))
);

-- Manager  ISA Person
CREATE TABLE Manager (
    person_id           INT,
    preferred_formation VARCHAR(20) NOT NULL,
    experience_level    VARCHAR(20) NOT NULL,
    PRIMARY KEY (person_id),
    FOREIGN KEY (person_id) REFERENCES Person(person_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Referee  ISA Person
CREATE TABLE Referee (
    person_id         INT,
    license_level     VARCHAR(20) NOT NULL,
    years_of_experience INT       NOT NULL,
    PRIMARY KEY (person_id),
    FOREIGN KEY (person_id) REFERENCES Person(person_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CHECK (years_of_experience >= 0)
);

-- Stadium
CREATE TABLE Stadium (
    stadium_id   INT,
    stadium_name VARCHAR(200) NOT NULL,
    city         VARCHAR(100) NOT NULL,
    capacity     INT          NOT NULL,
    PRIMARY KEY (stadium_id),
    UNIQUE (stadium_name, city),
    CHECK (capacity > 0)
);

-- Club
-- manager_id is nullable: a club may temporarily have no manager
CREATE TABLE Club (
    club_id         INT,
    club_name       VARCHAR(200) NOT NULL,
    city            VARCHAR(100),
    foundation_year INT,
    manager_id      INT,
    stadium_id      INT,
    PRIMARY KEY (club_id),
    UNIQUE (club_name),
    UNIQUE (manager_id),
    FOREIGN KEY (manager_id) REFERENCES Manager(person_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (stadium_id) REFERENCES Stadium(stadium_id)
);

-- Competition
CREATE TABLE Competition (
    competition_id   INT,
    name             VARCHAR(200) NOT NULL,
    season           VARCHAR(20)  NOT NULL,
    country          VARCHAR(100) NOT NULL,
    competition_type VARCHAR(20)  NOT NULL,
    PRIMARY KEY (competition_id),
    UNIQUE (name, season),
    CHECK (competition_type IN ('League','Cup','International'))
);

-- Match
-- home_goals / away_goals / attendance are NULL until referee submits
CREATE TABLE `Match` (
    match_id      INT,
    competition_id INT  NOT NULL,
    home_club_id  INT   NOT NULL,
    away_club_id  INT   NOT NULL,
    stadium_id    INT   NOT NULL,
    referee_id    INT   NOT NULL,
    match_datetime DATETIME NOT NULL,
    attendance    INT,
    home_goals    INT,
    away_goals    INT,
    PRIMARY KEY (match_id),
    FOREIGN KEY (competition_id) REFERENCES Competition(competition_id),
    FOREIGN KEY (home_club_id)   REFERENCES Club(club_id),
    FOREIGN KEY (away_club_id)   REFERENCES Club(club_id),
    FOREIGN KEY (stadium_id)     REFERENCES Stadium(stadium_id),
    FOREIGN KEY (referee_id)     REFERENCES Referee(person_id),
    CHECK (home_club_id <> away_club_id),
    CHECK (attendance  >= 0  OR attendance IS NULL),
    CHECK (home_goals  >= 0  OR home_goals IS NULL),
    CHECK (away_goals  >= 0  OR away_goals IS NULL),
    CHECK (
        (home_goals IS NULL AND away_goals IS NULL)
        OR (home_goals IS NOT NULL AND away_goals IS NOT NULL)
    )
);

-- Contract
CREATE TABLE Contract (
    contract_id   INT,
    player_id     INT          NOT NULL,
    club_id       INT          NOT NULL,
    start_date    DATE         NOT NULL,
    end_date      DATE         NOT NULL,
    weekly_wage   DECIMAL(12,2) NOT NULL,
    contract_type VARCHAR(20)  NOT NULL,
    PRIMARY KEY (contract_id),
    FOREIGN KEY (player_id) REFERENCES Player(person_id),
    FOREIGN KEY (club_id)   REFERENCES Club(club_id),
    CHECK (end_date > start_date),
    CHECK (weekly_wage > 0),
    CHECK (contract_type IN ('Permanent','Loan'))
);

-- Transfer_Record
-- from_club_id may be NULL for free-agent first contract
CREATE TABLE Transfer_Record (
    transfer_id   INT,
    player_id     INT          NOT NULL,
    from_club_id  INT,
    to_club_id    INT          NOT NULL,
    transfer_date DATE         NOT NULL,
    transfer_fee  DECIMAL(15,2) NOT NULL,
    transfer_type VARCHAR(20)  NOT NULL,
    PRIMARY KEY (transfer_id),
    FOREIGN KEY (player_id)    REFERENCES Player(person_id),
    FOREIGN KEY (from_club_id) REFERENCES Club(club_id),
    FOREIGN KEY (to_club_id)   REFERENCES Club(club_id),
    CHECK (transfer_fee >= 0),
    CHECK (transfer_type IN ('Free','Purchase','Loan')),
    CHECK (
        (transfer_type = 'Free'     AND transfer_fee = 0)
        OR (transfer_type IN ('Purchase','Loan') AND transfer_fee >= 0)
    ),
    CHECK (from_club_id IS NULL OR from_club_id <> to_club_id)
);

-- Match_Squad  (submitted by Manager, operation 5)
CREATE TABLE Match_Squad (
    player_id  INT,
    match_id   INT,
    club_id    INT     NOT NULL,
    is_starter BOOLEAN NOT NULL,
    PRIMARY KEY (player_id, match_id),
    FOREIGN KEY (player_id) REFERENCES Player(person_id),
    FOREIGN KEY (match_id)  REFERENCES `Match`(match_id),
    FOREIGN KEY (club_id)   REFERENCES Club(club_id)
);

-- Match_Stats  (submitted by Referee, operation 13)
CREATE TABLE Match_Stats (
    player_id        INT,
    match_id         INT,
    club_id          INT          NOT NULL,
    is_starter       BOOLEAN      NOT NULL,
    minutes_played   INT          NOT NULL,
    position_in_match VARCHAR(10) NOT NULL,
    goals            INT          NOT NULL,
    assists          INT          NOT NULL,
    yellow_cards     INT          NOT NULL,
    red_cards        BOOLEAN      NOT NULL,
    rating           DECIMAL(3,1) NOT NULL,
    PRIMARY KEY (player_id, match_id),
    FOREIGN KEY (player_id) REFERENCES Player(person_id),
    FOREIGN KEY (match_id)  REFERENCES `Match`(match_id),
    FOREIGN KEY (club_id)   REFERENCES Club(club_id),
    CHECK (minutes_played BETWEEN 0 AND 120),
    CHECK (goals       >= 0),
    CHECK (assists     >= 0),
    CHECK (yellow_cards BETWEEN 0 AND 2),
    CHECK (rating BETWEEN 1.0 AND 10.0)
);
