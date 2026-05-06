# TransferDB

TransferDB is a MySQL database schema for modeling football player transfers, contracts, clubs, competitions, matches, and match statistics.

This project was developed for **CMPE 321 - Database Management Systems**, Project 1, as a two-person team assignment. The repository version is cleaned for public GitHub presentation and focuses on the relational schema implementation.

## Features

- Relational model for football transfer and match management
- Person supertype with Player, Manager, and Referee subtypes
- Club, stadium, competition, contract, transfer, match, and match-stat tables
- Primary keys, foreign keys, uniqueness rules, and `CHECK` constraints
- Documented limitations for constraints that require cross-table, cross-row, or temporal validation
- MySQL-ready DDL script that recreates the `TransferDB` database

## Tech Stack

- SQL
- MySQL
- Relational database design

## Usage Flow

There is no application UI in this project. The main workflow is:

1. Run the schema script in a MySQL server.
2. Inspect the created `TransferDB` database and tables.
3. Extend the schema with seed data, queries, triggers, or stored procedures if needed.

## Running Locally

Prerequisites:

- MySQL Server
- MySQL CLI client

Run the schema:

```bash
mysql -u root -p < schema/transferdb_schema.sql
```

Verify the created tables:

```bash
mysql -u root -p -e "USE TransferDB; SHOW TABLES;"
```

The schema script starts with `DROP DATABASE IF EXISTS TransferDB`, so running it will recreate the database.

## Project Structure

```text
.
|-- reports/
|   |-- contribution-report-redacted.txt
|   |-- part1-conceptual-design.pdf
|   `-- part2-logical-design.pdf
|-- schema/
|   `-- transferdb_schema.sql
|-- .gitignore
`-- README.md
```

Course reports are included for public review with student IDs removed. Local editor/history artifacts remain excluded through `.gitignore`.

## Skills Demonstrated

- ER-to-relational schema mapping
- SQL DDL design
- Primary key and foreign key modeling
- ISA hierarchy implementation in relational databases
- Many-to-many relationship modeling
- Constraint analysis and documentation
- MySQL schema validation
- Repository cleanup for public presentation

## Suggested Repository Names

- `transferdb-mysql-schema`
- `football-transfer-database`
- `cmpe321-transferdb`
