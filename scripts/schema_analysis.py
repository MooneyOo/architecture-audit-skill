#!/usr/bin/env python3
"""
Schema Analysis Script

Analyzes database schemas from ORM definitions and generates documentation.
Supports SQL (Prisma, TypeORM, Sequelize, SQLAlchemy, Django) and NoSQL (Mongoose).

Usage:
    python schema_analysis.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: json)
    --diagram                 Include Mermaid ER diagram
    --tables                  Output table schemas only
    --cache                   Output cache documentation only
    --chunked                 Enable chunked processing for large projects
    --chunk-size N            Number of files per chunk (default: 100)
    --resume                  Resume from interrupted analysis
    --force                   Force re-analysis (ignore cache)
    --progress                Show progress bar
    --quiet                   Suppress progress output
    --help                    Show usage information
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

# Scalability imports
try:
    from chunked_analyzer import ChunkedAnalyzer, ChunkConfig, count_files
    from cache_manager import CacheManager
    from progress_tracker import ProgressTracker, SpinnerProgress
    SCALABILITY_AVAILABLE = True
except ImportError:
    SCALABILITY_AVAILABLE = False


class DatabaseType(Enum):
    POSTGRESQL = "PostgreSQL"
    MYSQL = "MySQL"
    SQLITE = "SQLite"
    MONGODB = "MongoDB"
    REDIS = "Redis"
    UNKNOWN = "Unknown"


class ORMType(Enum):
    PRISMA = "Prisma"
    TYPEORM = "TypeORM"
    SEQUELIZE = "Sequelize"
    SQLALCHEMY = "SQLAlchemy"
    DJANGO = "Django ORM"
    MONGOOSE = "Mongoose"
    UNKNOWN = "Unknown"


@dataclass
class Index:
    name: str
    columns: list[str]
    unique: bool = False
    index_type: str = "INDEX"  # INDEX, UNIQUE, PRIMARY


@dataclass
class Column:
    name: str
    data_type: str
    nullable: bool = True
    default: Optional[str] = None
    primary_key: bool = False
    foreign_key: Optional[str] = None  # table.column
    unique: bool = False
    constraints: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    indexes: list[Index] = field(default_factory=list)
    file_path: str = ""
    orm_type: str = ""


@dataclass
class Relationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    relation_type: str = "one-to-many"  # one-to-one, one-to-many, many-to-many


@dataclass
class CacheKey:
    pattern: str
    ttl: Optional[int] = None
    description: str = ""
    data_type: str = ""
    invalidation: str = ""


@dataclass
class CacheConfig:
    technology: str = "Redis"
    host: str = ""
    port: int = 6379
    default_ttl: int = 300


@dataclass
class SchemaAnalysisResult:
    project_path: str
    project_name: str
    database_type: DatabaseType = DatabaseType.UNKNOWN
    orm_type: ORMType = ORMType.UNKNOWN
    tables: list[Table] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    cache_config: Optional[CacheConfig] = None
    cache_keys: list[CacheKey] = field(default_factory=list)
    er_diagram: str = ""
    errors: list[str] = field(default_factory=list)


# Type mappings for different ORMs
PRISMA_TYPE_MAP = {
    "String": "VARCHAR(255)",
    "Int": "INTEGER",
    "BigInt": "BIGINT",
    "Float": "FLOAT",
    "Decimal": "DECIMAL",
    "Boolean": "BOOLEAN",
    "DateTime": "TIMESTAMP",
    "Json": "JSON",
    "Bytes": "BLOB",
}

TYPEORM_TYPE_MAP = {
    "int": "INTEGER",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "float": "FLOAT",
    "double": "DOUBLE",
    "decimal": "DECIMAL",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "varchar": "VARCHAR(255)",
    "text": "TEXT",
    "string": "VARCHAR(255)",
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "timestamp": "TIMESTAMP",
    "json": "JSON",
    "simple-json": "JSON",
    "uuid": "UUID",
}

SEQUELIZE_TYPE_MAP = {
    "STRING": "VARCHAR(255)",
    "CHAR": "CHAR",
    "TEXT": "TEXT",
    "INTEGER": "INTEGER",
    "BIGINT": "BIGINT",
    "FLOAT": "FLOAT",
    "DOUBLE": "DOUBLE",
    "DECIMAL": "DECIMAL",
    "BOOLEAN": "BOOLEAN",
    "DATE": "TIMESTAMP",
    "DATEONLY": "DATE",
    "JSON": "JSON",
    "JSONB": "JSONB",
    "UUID": "UUID",
    "UUIDV4": "UUID",
}

MONGOOSE_TYPE_MAP = {
    "String": "String",
    "Number": "Number",
    "Boolean": "Boolean",
    "Date": "Date",
    "ObjectId": "ObjectId",
    "Buffer": "Buffer",
    "Array": "Array",
    "Mixed": "Mixed",
}

DJANGO_TYPE_MAP = {
    "CharField": "VARCHAR",
    "TextField": "TEXT",
    "IntegerField": "INTEGER",
    "BigIntegerField": "BIGINT",
    "SmallIntegerField": "SMALLINT",
    "PositiveIntegerField": "INTEGER UNSIGNED",
    "FloatField": "FLOAT",
    "DecimalField": "DECIMAL",
    "BooleanField": "BOOLEAN",
    "DateField": "DATE",
    "DateTimeField": "TIMESTAMP",
    "TimeField": "TIME",
    "EmailField": "VARCHAR(254)",
    "URLField": "VARCHAR(200)",
    "UUIDField": "UUID",
    "JSONField": "JSON",
    "BinaryField": "BLOB",
    "AutoField": "SERIAL",
    "BigAutoField": "BIGSERIAL",
    "ForeignKey": "INTEGER",
    "OneToOneField": "INTEGER",
    "ManyToManyField": "INTEGER",
}


def detect_database_and_orm(project_path: Path) -> tuple[DatabaseType, ORMType, list[str]]:
    """Detect database and ORM type from project dependencies."""
    database_type = DatabaseType.UNKNOWN
    orm_type = ORMType.UNKNOWN
    errors = []

    # Define directories to check (root + common subdirectories)
    check_dirs = [project_path]
    for subdir in ["backend", "server", "api", "src"]:
        sub_path = project_path / subdir
        if sub_path.exists():
            check_dirs.append(sub_path)

    # Check for Node.js projects
    for check_path in check_dirs:
        package_json_path = check_path / "package.json"
        if package_json_path.exists():
            try:
                with open(package_json_path, 'r') as f:
                    data = json.load(f)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

                # Check for ORMs
                if "prisma" in str(deps).lower() or any(k for k in deps if "prisma" in k.lower()):
                    orm_type = ORMType.PRISMA
                    database_type = DatabaseType.POSTGRESQL  # Prisma default
                elif any(k for k in deps if "typeorm" in k.lower()):
                    orm_type = ORMType.TYPEORM
                    database_type = DatabaseType.POSTGRESQL
                elif any(k for k in deps if "sequelize" in k.lower()):
                    orm_type = ORMType.SEQUELIZE
                elif any(k for k in deps if "mongoose" in k.lower()):
                    orm_type = ORMType.MONGOOSE
                    database_type = DatabaseType.MONGODB

                # Detect database from drivers
                if "pg" in deps or "psycopg" in str(deps):
                    database_type = DatabaseType.POSTGRESQL
                elif "mysql" in deps or "mysql2" in deps:
                    database_type = DatabaseType.MYSQL
                elif "sqlite" in deps or "sqlite3" in deps:
                    database_type = DatabaseType.SQLITE

                break  # Found package.json, stop searching

            except Exception as e:
                errors.append(f"Error reading package.json: {e}")

    # Check for Python projects
    python_deps = []

    for check_path in check_dirs:
        requirements_path = check_path / "requirements.txt"
        pyproject_path = check_path / "pyproject.toml"

        if requirements_path.exists():
            try:
                with open(requirements_path, 'r') as f:
                    python_deps = [line.strip().lower() for line in f if line.strip() and not line.startswith('#')]
                break  # Found requirements.txt
            except Exception as e:
                errors.append(f"Error reading requirements.txt: {e}")

        if pyproject_path.exists():
            try:
                with open(pyproject_path, 'r') as f:
                    content = f.read()
                    # Extract dependencies from pyproject.toml
                    for line in content.split('\n'):
                        if '=' in line and not line.strip().startswith('#'):
                            parts = line.split('=')[0].strip().strip('"\'').lower()
                            if parts and not parts.startswith('['):
                                python_deps.append(parts)
                break  # Found pyproject.toml
            except Exception as e:
                errors.append(f"Error reading pyproject.toml: {e}")

    if python_deps:
        if any('sqlalchemy' in d for d in python_deps):
            orm_type = ORMType.SQLALCHEMY
        elif any('django' in d for d in python_deps):
            orm_type = ORMType.DJANGO

        # Detect database
        if any('psycopg' in d for d in python_deps):
            database_type = DatabaseType.POSTGRESQL
        elif any('mysql' in d for d in python_deps):
            database_type = DatabaseType.MYSQL
        elif any('sqlite' in d for d in python_deps):
            database_type = DatabaseType.SQLITE

    return database_type, orm_type, errors


def parse_prisma_schema(project_path: Path) -> tuple[list[Table], list[Relationship], list[str]]:
    """Parse Prisma schema files."""
    tables = []
    relationships = []
    errors = []

    schema_path = project_path / "prisma" / "schema.prisma"
    if not schema_path.exists():
        return tables, relationships, ["No Prisma schema found at prisma/schema.prisma"]

    try:
        with open(schema_path, 'r') as f:
            content = f.read()

        # Find all model blocks
        model_pattern = r'model\s+(\w+)\s*\{([^}]*)\}'
        for match in re.finditer(model_pattern, content, re.DOTALL):
            model_name = match.group(1)
            model_body = match.group(2)

            table = Table(
                name=model_name.lower() + "s",  # Prisma convention
                file_path=str(schema_path.relative_to(project_path)),
                orm_type="Prisma"
            )

            # Parse fields
            lines = model_body.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('//') or line.startswith('@@'):
                    continue

                # Parse field: fieldName Type @attributes
                field_match = re.match(r'(\w+)\s+(\w+)(\?)?(?:\s+(.*))?', line)
                if field_match:
                    field_name = field_match.group(1)
                    field_type = field_match.group(2)
                    nullable = field_match.group(3) == '?'
                    attrs = field_match.group(4) or ""

                    # Skip relation fields (arrays and objects without @id)
                    if field_type in ['[]', '{}'] or (field_type not in PRISMA_TYPE_MAP and '[' in field_type):
                        continue

                    # Determine SQL type
                    sql_type = PRISMA_TYPE_MAP.get(field_type, field_type.upper())

                    # Parse attributes
                    primary_key = '@id' in attrs
                    unique = '@unique' in attrs
                    default = None
                    default_match = re.search(r'@default\(([^)]+)\)', attrs)
                    if default_match:
                        default = default_match.group(1)

                    # Check for foreign key
                    foreign_key = None
                    relation_match = re.search(r'@relation\([^)]*fields:\s*\[(\w+)[^)]*\]', model_body)
                    if relation_match and field_name == relation_match.group(1):
                        foreign_key = field_type.lower() + "s.id"

                    column = Column(
                        name=field_name,
                        data_type=sql_type,
                        nullable=nullable,
                        default=default,
                        primary_key=primary_key,
                        unique=unique,
                        foreign_key=foreign_key
                    )
                    table.columns.append(column)

            # Parse @@index and @@unique
            for idx_match in re.finditer(r'@@index\(\[([^\]]+)\]', model_body):
                idx_cols = [c.strip().strip('"\'') for c in idx_match.group(1).split(',')]
                table.indexes.append(Index(name=f"idx_{model_name.lower()}", columns=idx_cols))

            for idx_match in re.finditer(r'@@unique\(\[([^\]]+)\]', model_body):
                idx_cols = [c.strip().strip('"\'') for c in idx_match.group(1).split(',')]
                table.indexes.append(Index(name=f"uq_{model_name.lower()}", columns=idx_cols, unique=True))

            if table.columns:
                tables.append(table)

    except Exception as e:
        errors.append(f"Error parsing Prisma schema: {e}")

    return tables, relationships, errors


def parse_typeorm_entities(project_path: Path) -> tuple[list[Table], list[Relationship], list[str]]:
    """Parse TypeORM entity files."""
    tables = []
    relationships = []
    errors = []

    # Find entity files
    entity_patterns = ["**/*.entity.ts", "**/*.Entity.ts", "**/entities/*.ts"]

    for pattern in entity_patterns:
        for entity_file in project_path.rglob(pattern.split("**/")[-1]):
            if "node_modules" in str(entity_file) or ".d.ts" in str(entity_file):
                continue

            try:
                with open(entity_file, 'r') as f:
                    content = f.read()

                # Find @Entity decorator
                entity_match = re.search(r'@Entity\(["\']?(\w+)["\']?\)', content)
                if not entity_match:
                    continue

                table_name = entity_match.group(1)
                table = Table(
                    name=table_name,
                    file_path=str(entity_file.relative_to(project_path)),
                    orm_type="TypeORM"
                )

                # Find class name for entity
                class_match = re.search(r'class\s+(\w+)\s+', content)
                class_name = class_match.group(1) if class_match else table_name

                # Parse columns - look for @PrimaryGeneratedColumn, @Column, @ManyToOne, etc.
                # Primary key
                for pk_match in re.finditer(r'@PrimaryGeneratedColumn\([^)]*\)\s*(?:public\s+)?(\w+):\s*(\w+)', content):
                    col_name = pk_match.group(1)
                    col_type = pk_match.group(2)
                    table.columns.append(Column(
                        name=col_name,
                        data_type=TYPEORM_TYPE_MAP.get(col_type.lower(), col_type.upper()),
                        primary_key=True,
                        nullable=False
                    ))

                # Regular columns
                for col_match in re.finditer(r'@Column\((?:\{([^}]*)\})?\)(?:\s*(?:public\s+)?(\w+):\s*(\w+))?', content):
                    attrs = col_match.group(1) or ""
                    col_name = col_match.group(2)
                    col_type = col_match.group(3)

                    if not col_name or not col_type:
                        continue

                    nullable = 'nullable:\s*true' in attrs
                    unique = 'unique:\s*true' in attrs
                    default = None
                    default_match = re.search(r'default:\s*["\']?([^"\'},]+)["\']?', attrs)
                    if default_match:
                        default = default_match.group(1)

                    table.columns.append(Column(
                        name=col_name,
                        data_type=TYPEORM_TYPE_MAP.get(col_type.lower(), col_type.upper()),
                        nullable=nullable,
                        default=default,
                        unique=unique
                    ))

                # Foreign keys from @ManyToOne
                for fk_match in re.finditer(r'@ManyToOne\([^)]+(?:\)\s*(?:public\s+)?(\w+):\s*(\w+))?', content):
                    col_name = fk_match.group(1)
                    ref_type = fk_match.group(2)
                    if col_name and ref_type:
                        table.columns.append(Column(
                            name=col_name + "Id",
                            data_type="INTEGER",
                            foreign_key=f"{ref_type.lower()}s.id"
                        ))

                if table.columns:
                    tables.append(table)

            except Exception as e:
                errors.append(f"Error parsing TypeORM entity {entity_file}: {e}")

    return tables, relationships, errors


def parse_sequelize_models(project_path: Path) -> tuple[list[Table], list[Relationship], list[str]]:
    """Parse Sequelize model files."""
    tables = []
    relationships = []
    errors = []

    # Find model files
    model_dirs = ["models", "src/models", "db/models"]

    for model_dir in model_dirs:
        model_path = project_path / model_dir
        if not model_path.exists():
            continue

        for model_file in model_path.glob("*.js"):
            if model_file.name in ["index.js", "associations.js"]:
                continue

            try:
                with open(model_file, 'r') as f:
                    content = f.read()

                # Find sequelize.define call
                define_match = re.search(r'sequelize\.define\(["\'](\w+)["\']\s*,\s*\{([^}]+)\}', content)
                if not define_match:
                    continue

                table_name = define_match.group(1)
                model_body = define_match.group(2)

                table = Table(
                    name=table_name,
                    file_path=str(model_file.relative_to(project_path)),
                    orm_type="Sequelize"
                )

                # Parse field definitions
                # Pattern: fieldName: { type: DataTypes.TYPE, ... }
                for field_match in re.finditer(r'(\w+):\s*\{([^}]+)\}', model_body):
                    field_name = field_match.group(1)
                    field_attrs = field_match.group(2)

                    # Extract type
                    type_match = re.search(r'type:\s*DataTypes\.(\w+)', field_attrs)
                    if not type_match:
                        continue
                    data_type = SEQUELIZE_TYPE_MAP.get(type_match.group(1), type_match.group(1))

                    # Extract constraints
                    nullable = 'allowNull:\s*true' in field_attrs
                    primary_key = 'primaryKey:\s*true' in field_attrs
                    unique = 'unique:\s*true' in field_attrs
                    default = None
                    default_match = re.search(r'defaultValue:\s*["\']?([^"\'}]+)["\']?', field_attrs)
                    if default_match:
                        default = default_match.group(1)

                    table.columns.append(Column(
                        name=field_name,
                        data_type=data_type,
                        nullable=nullable,
                        default=default,
                        primary_key=primary_key,
                        unique=unique
                    ))

                if table.columns:
                    tables.append(table)

            except Exception as e:
                errors.append(f"Error parsing Sequelize model {model_file}: {e}")

    return tables, relationships, errors


def parse_sqlalchemy_models(project_path: Path) -> tuple[list[Table], list[Relationship], list[str]]:
    """Parse SQLAlchemy model files."""
    tables = []
    relationships = []
    errors = []

    # Find model files - search recursively for all Python files with __tablename__
    model_files = []

    # Common model locations
    for pattern in ["**/models/*.py", "**/models.py", "**/model.py"]:
        for f in project_path.rglob(pattern.split("/")[-1] if "/" in pattern else pattern):
            if "__pycache__" not in str(f) and "test" not in str(f).lower():
                model_files.append(f)

    # Also search for any Python file containing __tablename__
    for py_file in project_path.rglob("*.py"):
        if "__pycache__" in str(py_file) or "test" in str(py_file).lower():
            continue
        if py_file not in model_files:
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                if "__tablename__" in content:
                    model_files.append(py_file)
            except:
                pass

    for model_file in model_files:
        try:
            with open(model_file, 'r') as f:
                content = f.read()

            # Find all class definitions
            class_starts = []
            for match in re.finditer(r'class\s+(\w+)\s*\([^)]*\):', content):
                class_starts.append((match.start(), match.end(), match.group(1)))

            # For each class, find its body and __tablename__
            for i, (start, end, class_name) in enumerate(class_starts):
                # Get class body (until next class or end of file)
                next_start = class_starts[i + 1][0] if i + 1 < len(class_starts) else len(content)
                class_body = content[start:next_start]

                # Find __tablename__ in class body
                table_match = re.search(r'__tablename__\s*=\s*["\'](\w+)["\']', class_body)
                if not table_match:
                    continue

                table_name = table_match.group(1)

                table = Table(
                    name=table_name,
                    file_path=str(model_file.relative_to(project_path)),
                    orm_type="SQLAlchemy"
                )

                # Parse columns - handle both traditional and mapped_column patterns

                # Pattern 1: Traditional: name = Column(Type, ...)
                for col_match in re.finditer(r'(\w+)\s*=\s*Column\(([^)]+)\)', class_body):
                    col_name = col_match.group(1)
                    col_def = col_match.group(2)

                    # Extract type
                    type_match = re.match(r'(\w+)', col_def)
                    if not type_match:
                        continue
                    data_type = type_match.group(1).upper()

                    # Extract constraints
                    primary_key = 'primary_key=True' in col_def
                    nullable = 'nullable=True' in col_def or (not primary_key and 'nullable' not in col_def)
                    unique = 'unique=True' in col_def
                    default = None
                    default_match = re.search(r'default=([^,)]+)', col_def)
                    if default_match:
                        default = default_match.group(1)

                    # Check for ForeignKey
                    foreign_key = None
                    fk_match = re.search(r'ForeignKey\(["\'](\w+)\.(\w+)["\']', col_def)
                    if fk_match:
                        foreign_key = f"{fk_match.group(1)}.{fk_match.group(2)}"

                        # Add relationship
                        relationships.append(Relationship(
                            from_table=table_name,
                            from_column=col_name,
                            to_table=fk_match.group(1),
                            to_column=fk_match.group(2)
                        ))

                    table.columns.append(Column(
                        name=col_name,
                        data_type=data_type,
                        nullable=nullable,
                        default=default,
                        primary_key=primary_key,
                        unique=unique,
                        foreign_key=foreign_key
                    ))

                # Pattern 2: Modern Mapped pattern: name: Mapped[Type] = mapped_column(...)
                for col_match in re.finditer(r'(\w+):\s*Mapped\[(?:Optional\[)?(\w+)\]?\s*=\s*mapped_column\(([^)]*)\)', class_body):
                    col_name = col_match.group(1)
                    type_hint = col_match.group(2)
                    col_def = col_match.group(3)

                    # Extract type from mapped_column arguments
                    type_match = re.search(r'(String|Text|Integer|Boolean|DateTime|Float|JSON|Text)\s*(?:\([^)]*\))?', col_def)
                    if type_match:
                        data_type = type_match.group(1).upper()
                        # Add size for String
                        size_match = re.search(r'String\((\d+)\)', col_def)
                        if size_match:
                            data_type = f"VARCHAR({size_match.group(1)})"
                    else:
                        # Infer from type hint
                        type_map = {
                            'int': 'INTEGER',
                            'str': 'VARCHAR',
                            'bool': 'BOOLEAN',
                            'datetime': 'TIMESTAMP',
                            'float': 'FLOAT',
                        }
                        data_type = type_map.get(type_hint.lower(), type_hint.upper())

                    # Extract constraints
                    primary_key = 'primary_key=True' in col_def
                    nullable = 'nullable=True' in col_def or 'Optional[' in col_match.group(0)
                    unique = 'unique=True' in col_def
                    default = None
                    default_match = re.search(r'default=([^,)]+)', col_def)
                    if default_match:
                        default = default_match.group(1).strip()

                    # Check for ForeignKey
                    foreign_key = None
                    fk_match = re.search(r'ForeignKey\(["\']([^"\']+)["\']', col_def)
                    if fk_match:
                        foreign_key = fk_match.group(1)
                        # Parse table.column format
                        parts = foreign_key.split('.')
                        if len(parts) == 2:
                            relationships.append(Relationship(
                                from_table=table_name,
                                from_column=col_name,
                                to_table=parts[0],
                                to_column=parts[1]
                            ))

                    table.columns.append(Column(
                        name=col_name,
                        data_type=data_type,
                        nullable=nullable,
                        default=default,
                        primary_key=primary_key,
                        unique=unique,
                        foreign_key=foreign_key
                    ))

                if table.columns:
                    tables.append(table)

        except Exception as e:
            errors.append(f"Error parsing SQLAlchemy models {model_file}: {e}")

    return tables, relationships, errors


def parse_django_models(project_path: Path) -> tuple[list[Table], list[Relationship], list[str]]:
    """Parse Django model files."""
    tables = []
    relationships = []
    errors = []

    # Find models.py files
    for models_file in project_path.rglob("models.py"):
        if "__pycache__" in str(models_file):
            continue
        # Skip if not in a Django app (no settings.py nearby)
        if not any((models_file.parent.parent / f).exists() for f in ["settings.py", "settings"]):
            continue

        try:
            with open(models_file, 'r') as f:
                content = f.read()

            # Find model classes
            class_pattern = r'class\s+(\w+)\(models\.Model\):\s*\n((?:\s{4,}.*\n)*)'

            for match in re.finditer(class_pattern, content):
                class_name = match.group(1)
                class_body = match.group(2)

                # Django table naming: app_modelname
                app_name = models_file.parent.name
                table_name = f"{app_name}_{class_name.lower()}"

                table = Table(
                    name=table_name,
                    file_path=str(models_file.relative_to(project_path)),
                    orm_type="Django ORM"
                )

                # Add implicit id field
                table.columns.append(Column(
                    name="id",
                    data_type="SERIAL",
                    primary_key=True,
                    nullable=False
                ))

                # Parse field definitions
                for field_match in re.finditer(r'(\w+)\s*=\s*models\.(\w+)(?:Field)?\(([^)]*)\)', class_body):
                    field_name = field_match.group(1)
                    field_type = field_match.group(2)
                    field_args = field_match.group(3)

                    # Map Django type to SQL type
                    data_type = DJANGO_TYPE_MAP.get(field_type, "VARCHAR")

                    # Extract constraints
                    nullable = 'null=True' in field_args or 'blank=True' in field_args
                    unique = 'unique=True' in field_args
                    default = None
                    default_match = re.search(r'default=([^,)]+)', field_args)
                    if default_match:
                        default = default_match.group(1)

                    # Handle ForeignKey
                    foreign_key = None
                    if field_type in ["ForeignKey", "OneToOneField"]:
                        fk_ref_match = re.search(r'["\'](\w+)\.(\w+)["\']', field_args)
                        if fk_ref_match:
                            foreign_key = f"{fk_ref_match.group(1).lower()}.{fk_ref_match.group(2)}"
                        # Add _id suffix for FK
                        field_name = field_name + "_id"

                    table.columns.append(Column(
                        name=field_name,
                        data_type=data_type,
                        nullable=nullable,
                        default=default,
                        unique=unique,
                        foreign_key=foreign_key
                    ))

                if len(table.columns) > 1:  # More than just id
                    tables.append(table)

        except Exception as e:
            errors.append(f"Error parsing Django models {models_file}: {e}")

    return tables, relationships, errors


def parse_mongoose_schemas(project_path: Path) -> tuple[list[Table], list[Relationship], list[str]]:
    """Parse Mongoose schema files."""
    tables = []
    relationships = []
    errors = []

    # Find model files
    model_dirs = ["models", "src/models", "db/models"]

    for model_dir in model_dirs:
        model_path = project_path / model_dir
        if not model_path.exists():
            continue

        for model_file in model_path.glob("*.js"):
            try:
                with open(model_file, 'r') as f:
                    content = f.read()

                # Find new mongoose.Schema calls
                schema_pattern = r'(?:const|let|var)\s+(\w+)Schema\s*=\s*new\s+mongoose\.Schema\(\s*\{([^}]+)\}'
                for match in re.finditer(schema_pattern, content, re.DOTALL):
                    schema_name = match.group(1)
                    schema_body = match.group(2)

                    # Infer collection name (usually lowercase plural)
                    collection_name = schema_name.replace("Schema", "").lower() + "s"

                    table = Table(
                        name=collection_name,
                        file_path=str(model_file.relative_to(project_path)),
                        orm_type="Mongoose"
                    )

                    # Add implicit _id field
                    table.columns.append(Column(
                        name="_id",
                        data_type="ObjectId",
                        primary_key=True,
                        nullable=False
                    ))

                    # Parse field definitions
                    # Pattern: fieldName: { type: Type, ... } or fieldName: Type
                    for field_match in re.finditer(r'(\w+):\s*(?:\{|(?:String|Number|Boolean|Date|ObjectId|Buffer|Array|Mixed))', schema_body):
                        field_name = field_match.group(1)
                        if field_name in ["_id", "id", "__v"]:
                            continue

                        # Get remaining content for this field
                        remaining = schema_body[field_match.end():]

                        # Simple type: fieldName: Type,
                        simple_match = re.match(r'^\s*(String|Number|Boolean|Date|ObjectId|Buffer|Array|Mixed)', schema_body[field_match.start():])
                        if simple_match:
                            table.columns.append(Column(
                                name=field_name,
                                data_type=simple_match.group(1)
                            ))
                            continue

                        # Complex type: fieldName: { type: Type, ... }
                        type_match = re.search(r'type:\s*(?:String|Number|Boolean|Date|ObjectId|Buffer|Array|Mixed|mongoose\.Schema\.Types\.ObjectId)', remaining[:200])
                        if type_match:
                            field_type = type_match.group(0).replace("type: ", "").replace("mongoose.Schema.Types.", "")
                            field_attrs = remaining[:200]

                            # Extract constraints
                            nullable = 'required:\s*true' not in field_attrs
                            unique = 'unique:\s*true' in field_attrs
                            default = None
                            default_match = re.search(r'default:\s*([^,}]+)', field_attrs)
                            if default_match:
                                default = default_match.group(1).strip()

                            # Check for enum
                            enum_match = re.search(r'enum:\s*\[([^\]]+)\]', field_attrs)
                            constraints = []
                            if enum_match:
                                constraints.append(f"enum: {enum_match.group(1)}")

                            # Check for reference
                            foreign_key = None
                            ref_match = re.search(r'ref:\s*["\'](\w+)["\']', field_attrs)
                            if ref_match:
                                foreign_key = f"{ref_match.group(1).lower()}s._id"

                            table.columns.append(Column(
                                name=field_name,
                                data_type=field_type,
                                nullable=nullable,
                                default=default,
                                unique=unique,
                                foreign_key=foreign_key,
                                constraints=constraints
                            ))

                    if len(table.columns) > 1:
                        tables.append(table)

                # Also find model registration
                model_pattern = r'mongoose\.model\(["\'](\w+)["\']\s*,\s*(\w+)Schema\)'
                for match in re.finditer(model_pattern, content):
                    model_name = match.group(1)
                    # Update table name to match model name
                    for table in tables:
                        if table.file_path == str(model_file.relative_to(project_path)):
                            if table.name.startswith(model_name.lower()[:4]):
                                break

            except Exception as e:
                errors.append(f"Error parsing Mongoose schema {model_file}: {e}")

    return tables, relationships, errors


def detect_cache_patterns(project_path: Path) -> tuple[Optional[CacheConfig], list[CacheKey], list[str]]:
    """Detect Redis/Memcached usage patterns."""
    cache_config = None
    cache_keys = []
    errors = []

    # Patterns for Redis detection
    redis_patterns = [
        r'(?:new\s+Redis\(|redis\.Redis\(|createClient\()',
        r'\.(?:get|set|setex|del|expire)\s*\(\s*["\']([^"\']+)["\']',
        r'\.(?:get|set|setex|del|expire)\s*\(\s*`([^`]+)`',
    ]

    # Patterns for key templates
    key_patterns = [
        r'["\']([a-zA-Z_]+:[a-zA-Z_{}:\-]+)["\']',
        r'`([a-zA-Z_]+:[a-zA-Z_\${}:\-]+)`',
        r'["\']([a-zA-Z_]+:[a-zA-Z_]+)["\']',
    ]

    # TTL patterns
    ttl_patterns = [
        r'(?:setex|EX|TTL|expire)\s*[,\(]\s*(\d+)',
        r'(?:setex|expire).*?(\d+)\s*(?:second|minute|hour|day)',
    ]

    # Find cache usage
    for ext in ["*.ts", "*.js", "*.py"]:
        for file_path in project_path.rglob(ext.split("*")[-1]):
            if "node_modules" in str(file_path) or "__pycache__" in str(file_path):
                continue
            if "test" in str(file_path).lower():
                continue

            try:
                with open(file_path, 'r') as f:
                    content = f.read()

                # Check for Redis usage
                if not cache_config and re.search(redis_patterns[0], content):
                    cache_config = CacheConfig(technology="Redis")

                # Find key patterns
                for pattern in key_patterns:
                    for match in re.finditer(pattern, content):
                        key_pattern = match.group(1)
                        # Clean up template variables
                        key_clean = re.sub(r'\{[^}]+\}', '{id}', key_pattern)
                        key_clean = re.sub(r'\$\{[^}]+\}', '{id}', key_clean)
                        key_clean = re.sub(r'\$\w+', '{id}', key_clean)

                        # Skip if too generic or looks like code
                        if len(key_clean) < 3 or key_clean in ['id', 'key', 'name']:
                            continue

                        # Check if already in list
                        if not any(k.pattern == key_clean for k in cache_keys):
                            cache_keys.append(CacheKey(
                                pattern=key_clean,
                                description=f"Cache key pattern from {file_path.name}"
                            ))

            except Exception as e:
                errors.append(f"Error scanning cache patterns in {file_path}: {e}")

    # Deduplicate and limit
    seen = set()
    unique_keys = []
    for key in cache_keys:
        if key.pattern not in seen and len(unique_keys) < 20:
            seen.add(key.pattern)
            unique_keys.append(key)

    return cache_config, unique_keys, errors


def generate_er_diagram(tables: list[Table], relationships: list[Relationship]) -> str:
    """Generate Mermaid erDiagram from tables and relationships."""
    if not tables:
        return ""

    lines = ["```mermaid", "erDiagram"]

    # Generate entity blocks
    for table in tables:
        # Use uppercase table name for entity
        entity_name = table.name.upper().replace("_", " ")
        entity_id = table.name.lower().replace("_", "_")

        lines.append(f"    {entity_id} {{")
        for col in table.columns[:10]:  # Limit columns
            type_str = col.data_type.split("(")[0].lower()  # Remove size
            annotations = []
            if col.primary_key:
                annotations.append("PK")
            if col.foreign_key:
                annotations.append("FK")
            if col.unique:
                annotations.append("UK")
            annot_str = " " + " ".join(annotations) if annotations else ""
            lines.append(f"        {type_str} {col.name}{annot_str}")
        if len(table.columns) > 10:
            lines.append(f"        // ... {len(table.columns) - 10} more columns")
        lines.append("    }")

    lines.append("")

    # Generate relationships
    processed_rels = set()

    # First, process explicit relationships
    for rel in relationships:
        from_id = rel.from_table.lower().replace("-", "_")
        to_id = rel.to_table.lower().replace("-", "_")
        rel_key = (from_id, to_id)

        if rel_key not in processed_rels:
            processed_rels.add(rel_key)
            # Determine relationship symbol
            if rel.relation_type == "one-to-one":
                symbol = "||--||"
            elif rel.relation_type == "many-to-many":
                symbol = "}o--o{"
            else:  # one-to-many
                symbol = "||--o{"
            lines.append(f"    {from_id} {symbol} {to_id} : \"{rel.from_column}\"")

    # Then, infer relationships from foreign keys
    for table in tables:
        for col in table.columns:
            if col.foreign_key:
                parts = col.foreign_key.split(".")
                if len(parts) == 2:
                    ref_table = parts[0].lower().replace("-", "_")
                    from_id = table.name.lower().replace("-", "_")

                    rel_key = (from_id, ref_table)
                    if rel_key not in processed_rels:
                        processed_rels.add(rel_key)
                        lines.append(f"    {from_id} }}o--|| {ref_table} : \"{col.name}\"")

    lines.append("```")
    return "\n".join(lines)


def analyze_project(project_path: str) -> SchemaAnalysisResult:
    """Analyze a project for database schemas."""
    path = Path(project_path)

    if not path.exists():
        return SchemaAnalysisResult(
            project_path=project_path,
            project_name=path.name,
            errors=[f"Project path does not exist: {project_path}"]
        )

    result = SchemaAnalysisResult(
        project_path=str(path),
        project_name=path.name
    )

    # Detect database and ORM
    result.database_type, result.orm_type, errors = detect_database_and_orm(path)
    result.errors.extend(errors)

    # Parse schemas based on ORM type
    if result.orm_type == ORMType.PRISMA:
        tables, relationships, errors = parse_prisma_schema(path)
        result.tables.extend(tables)
        result.relationships.extend(relationships)
        result.errors.extend(errors)

    elif result.orm_type == ORMType.TYPEORM:
        tables, relationships, errors = parse_typeorm_entities(path)
        result.tables.extend(tables)
        result.relationships.extend(relationships)
        result.errors.extend(errors)

    elif result.orm_type == ORMType.SEQUELIZE:
        tables, relationships, errors = parse_sequelize_models(path)
        result.tables.extend(tables)
        result.relationships.extend(relationships)
        result.errors.extend(errors)

    elif result.orm_type == ORMType.SQLALCHEMY:
        tables, relationships, errors = parse_sqlalchemy_models(path)
        result.tables.extend(tables)
        result.relationships.extend(relationships)
        result.errors.extend(errors)

    elif result.orm_type == ORMType.DJANGO:
        tables, relationships, errors = parse_django_models(path)
        result.tables.extend(tables)
        result.relationships.extend(relationships)
        result.errors.extend(errors)

    elif result.orm_type == ORMType.MONGOOSE:
        tables, relationships, errors = parse_mongoose_schemas(path)
        result.tables.extend(tables)
        result.relationships.extend(relationships)
        result.errors.extend(errors)

    # Detect cache patterns
    cache_config, cache_keys, errors = detect_cache_patterns(path)
    result.cache_config = cache_config
    result.cache_keys = cache_keys
    result.errors.extend(errors)

    # Generate ER diagram
    if result.tables:
        result.er_diagram = generate_er_diagram(result.tables, result.relationships)

    return result


# ============================================================================
# Schema Completeness Check (Epic-8)
# ============================================================================

@dataclass
class CompletenessIssue:
    """Represents a schema documentation completeness issue."""
    issue_type: str  # 'missing_documentation', 'extra_documentation', 'missing_fk_table'
    table: str
    column: Optional[str] = None
    references: Optional[str] = None
    message: str = ""
    file_path: Optional[str] = None


@dataclass
class CompletenessResult:
    """Result of schema documentation completeness check."""
    detected_models: dict[str, str]  # model_name -> file_path
    documented_tables: set[str]
    coverage_percentage: float
    issues: list[CompletenessIssue] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return len([i for i in self.issues if i.issue_type in ('missing_documentation', 'missing_fk_table')]) == 0


def check_schema_completeness(
    detected_tables: list[Table],
    documented_table_names: set[str]
) -> CompletenessResult:
    """
    Check if all detected ORM models are properly documented.

    Args:
        detected_tables: List of Table objects detected from ORM analysis
        documented_table_names: Set of table names that are documented

    Returns:
        CompletenessResult with coverage info and issues
    """
    # Build detected models dict
    detected_models = {t.name: t.file_path for t in detected_tables}
    detected_set = set(detected_models.keys())

    issues = []

    # Missing documentation: detected but not documented
    missing = detected_set - documented_table_names
    for model in missing:
        issues.append(CompletenessIssue(
            issue_type='missing_documentation',
            table=model,
            file_path=detected_models.get(model),
            message=f"Model '{model}' detected but not documented"
        ))

    # Extra documentation: documented but not detected (might be stale)
    extra = documented_table_names - detected_set
    for table in extra:
        issues.append(CompletenessIssue(
            issue_type='extra_documentation',
            table=table,
            message=f"Table '{table}' documented but no model found (possibly stale)"
        ))

    # Verify foreign keys reference documented tables
    all_table_names = detected_set | documented_table_names
    for table in detected_tables:
        for col in table.columns:
            if col.foreign_key:
                # Parse FK reference (format: table.column)
                parts = col.foreign_key.split('.')
                if len(parts) >= 1:
                    fk_table = parts[0]
                    if fk_table not in all_table_names:
                        issues.append(CompletenessIssue(
                            issue_type='missing_fk_table',
                            table=table.name,
                            column=col.name,
                            references=col.foreign_key,
                            message=f"FK '{col.name}' references undocumented table '{fk_table}'"
                        ))

    # Calculate coverage
    if not detected_set:
        coverage = 100.0  # No models to document
    else:
        covered = detected_set & documented_table_names
        coverage = round(len(covered) / len(detected_set) * 100, 1)

    return CompletenessResult(
        detected_models=detected_models,
        documented_tables=documented_table_names,
        coverage_percentage=coverage,
        issues=issues
    )


def verify_foreign_keys(tables: list[Table]) -> list[CompletenessIssue]:
    """
    Verify all foreign keys reference valid tables.

    Args:
        tables: List of detected Table objects

    Returns:
        List of issues with foreign key references
    """
    issues = []
    table_names = {t.name for t in tables}

    for table in tables:
        for col in table.columns:
            if col.foreign_key:
                parts = col.foreign_key.split('.')
                if len(parts) >= 1:
                    fk_table = parts[0]
                    if fk_table not in table_names:
                        issues.append(CompletenessIssue(
                            issue_type='missing_fk_table',
                            table=table.name,
                            column=col.name,
                            references=col.foreign_key,
                            message=f"FK '{col.name}' in '{table.name}' references unknown table '{fk_table}'"
                        ))

    return issues


def output_completeness_markdown(result: CompletenessResult) -> str:
    """Format completeness result as Markdown."""
    lines = ["## Schema Documentation Completeness\n"]

    # Coverage Summary
    lines.append("### Coverage Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Models Detected | {len(result.detected_models)} |")
    lines.append(f"| Models Documented | {len(result.documented_tables & set(result.detected_models.keys()))} |")
    lines.append(f"| Coverage | {result.coverage_percentage}% |")
    lines.append("")

    # Missing Documentation
    missing = [i for i in result.issues if i.issue_type == 'missing_documentation']
    if missing:
        lines.append("### Missing Documentation\n")
        lines.append("| Model | Source File |")
        lines.append("|-------|-------------|")
        for issue in missing:
            lines.append(f"| {issue.table} | `{issue.file_path or 'unknown'}` |")
        lines.append("")

    # Extra Documentation
    extra = [i for i in result.issues if i.issue_type == 'extra_documentation']
    if extra:
        lines.append("### Extra Documentation (No Model Found)\n")
        lines.append("| Table | Possible Cause |")
        lines.append("|-------|----------------|")
        for issue in extra:
            lines.append(f"| {issue.table} | Removed model, stale docs |")
        lines.append("")

    # Foreign Key Issues
    fk_issues = [i for i in result.issues if i.issue_type == 'missing_fk_table']
    if fk_issues:
        lines.append("### Foreign Key Issues\n")
        lines.append("| Table | Column | References | Issue |")
        lines.append("|-------|--------|------------|-------|")
        for issue in fk_issues:
            lines.append(f"| {issue.table} | {issue.column} | {issue.references} | Undocumented table |")
        lines.append("")

    # Status
    if result.is_complete:
        lines.append("**Status:** ✓ Schema documentation is complete\n")
    else:
        lines.append(f"**Status:** ✗ {len(missing)} missing, {len(extra)} extra, {len(fk_issues)} FK issues\n")

    return "\n".join(lines)


def output_completeness_json(result: CompletenessResult) -> str:
    """Format completeness result as JSON."""
    output = {
        "coverage_percentage": result.coverage_percentage,
        "detected_count": len(result.detected_models),
        "documented_count": len(result.documented_tables & set(result.detected_models.keys())),
        "is_complete": result.is_complete,
        "issues": [
            {
                "type": i.issue_type,
                "table": i.table,
                "column": i.column,
                "references": i.references,
                "message": i.message,
                "file_path": i.file_path
            }
            for i in result.issues
        ],
        "detected_models": result.detected_models
    }
    return json.dumps(output, indent=2)


# ============================================================================


def output_json(result: SchemaAnalysisResult) -> str:
    """Format results as JSON."""
    output = {
        "project_path": result.project_path,
        "project_name": result.project_name,
        "database_type": result.database_type.value,
        "orm_type": result.orm_type.value,
        "table_count": len(result.tables),
        "tables": [
            {
                "name": t.name,
                "orm_type": t.orm_type,
                "file_path": t.file_path,
                "columns": [
                    {
                        "name": c.name,
                        "type": c.data_type,
                        "nullable": c.nullable,
                        "default": c.default,
                        "primary_key": c.primary_key,
                        "foreign_key": c.foreign_key,
                        "unique": c.unique,
                        "constraints": c.constraints
                    }
                    for c in t.columns
                ],
                "indexes": [
                    {
                        "name": idx.name,
                        "columns": idx.columns,
                        "unique": idx.unique
                    }
                    for idx in t.indexes
                ]
            }
            for t in result.tables
        ],
        "relationships": [
            {
                "from_table": r.from_table,
                "from_column": r.from_column,
                "to_table": r.to_table,
                "to_column": r.to_column,
                "type": r.relation_type
            }
            for r in result.relationships
        ],
        "cache": {
            "config": {
                "technology": result.cache_config.technology,
                "host": result.cache_config.host,
                "port": result.cache_config.port,
                "default_ttl": result.cache_config.default_ttl
            } if result.cache_config else None,
            "keys": [
                {
                    "pattern": k.pattern,
                    "ttl": k.ttl,
                    "description": k.description
                }
                for k in result.cache_keys
            ]
        },
        "er_diagram": result.er_diagram,
        "errors": result.errors
    }

    return json.dumps(output, indent=2)


def output_markdown(result: SchemaAnalysisResult, sections: dict = None) -> str:
    """Format results as Markdown."""
    sections = sections or {
        "database": True,
        "diagram": True,
        "tables": True,
        "relationships": True,
        "cache": True
    }

    lines = [f"# Data Layer & Schema Analysis\n"]
    lines.append(f"**Project:** `{result.project_path}`\n")
    lines.append(f"**Project Name:** {result.project_name}\n")

    if result.errors:
        lines.append("## Errors\n")
        for error in result.errors[:10]:
            lines.append(f"- {error}\n")
        lines.append("")

    # Database Configuration
    if sections.get("database"):
        lines.append("## Database Configuration\n")
        lines.append("| Property | Value |")
        lines.append("|----------|-------|")
        lines.append(f"| Database | {result.database_type.value} |")
        lines.append(f"| ORM | {result.orm_type.value} |")
        lines.append(f"| Tables Found | {len(result.tables)} |")
        lines.append("")

    # ER Diagram
    if sections.get("diagram") and result.er_diagram:
        lines.append("## ER Diagram\n")
        lines.append(result.er_diagram)
        lines.append("")

    # Table Schemas
    if sections.get("tables") and result.tables:
        lines.append("## Table Schemas\n")

        for table in result.tables:
            lines.append(f"### {table.name}\n")

            if table.file_path:
                lines.append(f"**File:** `{table.file_path}`  ")
            if table.orm_type:
                lines.append(f"**ORM:** {table.orm_type}\n")

            lines.append("| Column | Type | Nullable | Default | Constraints |")
            lines.append("|--------|------|----------|---------|-------------|")

            for col in table.columns:
                constraints = []
                if col.primary_key:
                    constraints.append("PRIMARY KEY")
                if col.unique:
                    constraints.append("UNIQUE")
                if col.foreign_key:
                    constraints.append(f"FK: {col.foreign_key}")
                constraints.extend(col.constraints)

                lines.append(f"| {col.name} | {col.data_type} | {'Yes' if col.nullable else 'No'} | {col.default or '-'} | {', '.join(constraints) or '-'} |")

            if table.indexes:
                lines.append("\n**Indexes:**\n")
                for idx in table.indexes:
                    idx_type = "UNIQUE" if idx.unique else "INDEX"
                    lines.append(f"- {idx_type}: {', '.join(idx.columns)}")

            lines.append("")

    # Relationships
    if sections.get("relationships") and result.relationships:
        lines.append("## Relationships\n")
        lines.append("| From Table | From Column | To Table | To Column | Type |")
        lines.append("|------------|-------------|----------|-----------|------|")

        for rel in result.relationships:
            lines.append(f"| {rel.from_table} | {rel.from_column} | {rel.to_table} | {rel.to_column} | {rel.relation_type} |")

        lines.append("")

    # Cache Layer
    if sections.get("cache") and (result.cache_config or result.cache_keys):
        lines.append("## Cache Layer\n")

        if result.cache_config:
            lines.append("### Cache Configuration\n")
            lines.append("| Property | Value |")
            lines.append("|----------|-------|")
            lines.append(f"| Technology | {result.cache_config.technology} |")
            lines.append(f"| Default TTL | {result.cache_config.default_ttl}s |")
            lines.append("")

        if result.cache_keys:
            lines.append("### Cache Keys\n")
            lines.append("| Key Pattern | TTL | Description |")
            lines.append("|-------------|-----|-------------|")

            for key in result.cache_keys[:15]:
                ttl_str = f"{key.ttl}s" if key.ttl else "-"
                lines.append(f"| `{key.pattern}` | {ttl_str} | {key.description} |")

            lines.append("")

    return "\n".join(lines)


# ============================================================================
# Chunked Analysis Support (Epic 4)
# ============================================================================

def analyze_project_chunked(
    project_path: str,
    chunk_size: int = 100,
    resume: bool = True,
    force: bool = False,
    show_progress: bool = False,
    quiet: bool = False
) -> SchemaAnalysisResult:
    """
    Analyze a project using chunked processing for large codebases.

    Args:
        project_path: Path to the project
        chunk_size: Number of files per chunk
        resume: Resume from interrupted analysis
        force: Force re-analysis (ignore cache)
        show_progress: Show progress bar
        quiet: Suppress progress output

    Returns:
        SchemaAnalysisResult with analysis results
    """
    if not SCALABILITY_AVAILABLE:
        # Fall back to regular analysis if modules not available
        return analyze_project(project_path)

    path = Path(project_path)

    if not path.exists():
        return SchemaAnalysisResult(
            project_path=project_path,
            project_name=path.name,
            errors=[f"Project path does not exist: {project_path}"]
        )

    result = SchemaAnalysisResult(
        project_path=str(path),
        project_name=path.name
    )

    # Detect database and ORM (quick operation)
    result.database_type, result.orm_type, errors = detect_database_and_orm(path)
    result.errors.extend(errors)

    # Setup cache
    cache_dir = path / ".audit_cache" / "schema_analysis"
    cache = CacheManager(cache_dir)

    if force:
        cache.invalidate()

    # Setup progress tracking
    total_files = count_files(path)
    progress = None
    if show_progress and not quiet:
        progress = ProgressTracker(
            total=total_files,
            phase="Schema analysis",
            quiet=quiet
        )

    # Configure chunked analyzer
    config = ChunkConfig(
        chunk_size=chunk_size,
        output_dir=cache_dir / "chunks",
        resume=resume,
        file_extensions={'.py', '.ts', '.js', '.prisma'}  # Schema-related files
    )

    analyzer = ChunkedAnalyzer(config)

    # Define analyzer function based on ORM type
    def analyze_schema_file(file_path: Path) -> dict:
        """Analyze a single schema file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tables = []
            relationships = []

            # Determine file type and parse accordingly
            if file_path.suffix == '.prisma' and result.orm_type == ORMType.PRISMA:
                # Parse Prisma schema
                model_pattern = r'model\s+(\w+)\s*\{([^}]*)\}'
                for match in re.finditer(model_pattern, content, re.DOTALL):
                    model_name = match.group(1)
                    model_body = match.group(2)
                    table = _parse_prisma_model(model_name, model_body, file_path, path)
                    if table:
                        tables.append(table)

            elif file_path.suffix in {'.ts', '.js'}:
                if result.orm_type == ORMType.TYPEORM:
                    # Check for TypeORM entity
                    if '@Entity' in content:
                        table = _parse_typeorm_entity(content, file_path, path)
                        if table:
                            tables.append(table)
                elif result.orm_type == ORMType.MONGOOSE:
                    if 'mongoose.Schema' in content:
                        table = _parse_mongoose_schema(content, file_path, path)
                        if table:
                            tables.append(table)

            elif file_path.suffix == '.py':
                if result.orm_type == ORMType.SQLALCHEMY:
                    if '__tablename__' in content:
                        parsed_tables, parsed_rels = _parse_sqlalchemy_file(content, file_path, path)
                        tables.extend(parsed_tables)
                        relationships.extend(parsed_rels)
                elif result.orm_type == ORMType.DJANGO:
                    if 'models.Model' in content:
                        parsed_tables = _parse_django_file(content, file_path, path)
                        tables.extend(parsed_tables)

            return {
                "file": str(file_path),
                "tables": tables,
                "relationships": relationships
            }

        except Exception as e:
            return {"file": str(file_path), "error": str(e)}

    # Process in chunks
    all_tables = []
    all_relationships = []

    for chunk_result in analyzer.analyze_project(path, analyze_schema_file):
        for file_result in chunk_result.results:
            if "tables" in file_result:
                all_tables.extend(file_result["tables"])
            if "relationships" in file_result:
                all_relationships.extend(file_result["relationships"])
            if "error" in file_result:
                result.errors.append(f"Error in {file_result['file']}: {file_result['error']}")

        if progress:
            progress.update(chunk_result.files_processed)

    if progress:
        progress.complete()

    # Deduplicate tables by name
    seen_tables = set()
    unique_tables = []
    for table in all_tables:
        if table.name not in seen_tables:
            seen_tables.add(table.name)
            unique_tables.append(table)

    result.tables = unique_tables
    result.relationships = all_relationships

    # Detect cache patterns (separate pass)
    cache_config, cache_keys, errors = detect_cache_patterns(path)
    result.cache_config = cache_config
    result.cache_keys = cache_keys
    result.errors.extend(errors)

    # Generate ER diagram
    if result.tables:
        result.er_diagram = generate_er_diagram(result.tables, result.relationships)

    return result


# Helper functions for chunked file parsing

def _parse_prisma_model(model_name: str, model_body: str, file_path: Path, project_path: Path) -> Optional[Table]:
    """Parse a single Prisma model."""
    table = Table(
        name=model_name.lower() + "s",
        file_path=str(file_path.relative_to(project_path)),
        orm_type="Prisma"
    )

    lines = model_body.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('//') or line.startswith('@@'):
            continue

        field_match = re.match(r'(\w+)\s+(\w+)(\?)?(?:\s+(.*))?', line)
        if field_match:
            field_name = field_match.group(1)
            field_type = field_match.group(2)
            nullable = field_match.group(3) == '?'
            attrs = field_match.group(4) or ""

            if field_type in ['[]', '{}'] or (field_type not in PRISMA_TYPE_MAP and '[' in field_type):
                continue

            sql_type = PRISMA_TYPE_MAP.get(field_type, field_type.upper())
            primary_key = '@id' in attrs
            unique = '@unique' in attrs
            default = None
            default_match = re.search(r'@default\(([^)]+)\)', attrs)
            if default_match:
                default = default_match.group(1)

            column = Column(
                name=field_name,
                data_type=sql_type,
                nullable=nullable,
                default=default,
                primary_key=primary_key,
                unique=unique
            )
            table.columns.append(column)

    return table if table.columns else None


def _parse_typeorm_entity(content: str, file_path: Path, project_path: Path) -> Optional[Table]:
    """Parse a TypeORM entity file."""
    entity_match = re.search(r'@Entity\(["\']?(\w+)["\']?\)', content)
    if not entity_match:
        return None

    table_name = entity_match.group(1)
    table = Table(
        name=table_name,
        file_path=str(file_path.relative_to(project_path)),
        orm_type="TypeORM"
    )

    # Parse columns
    for pk_match in re.finditer(r'@PrimaryGeneratedColumn\([^)]*\)\s*(?:public\s+)?(\w+):\s*(\w+)', content):
        table.columns.append(Column(
            name=pk_match.group(1),
            data_type=TYPEORM_TYPE_MAP.get(pk_match.group(2).lower(), pk_match.group(2).upper()),
            primary_key=True,
            nullable=False
        ))

    for col_match in re.finditer(r'@Column\((?:\{([^}]*)\})?\)(?:\s*(?:public\s+)?(\w+):\s*(\w+))?', content):
        attrs = col_match.group(1) or ""
        col_name = col_match.group(2)
        col_type = col_match.group(3)

        if not col_name or not col_type:
            continue

        table.columns.append(Column(
            name=col_name,
            data_type=TYPEORM_TYPE_MAP.get(col_type.lower(), col_type.upper()),
            nullable='nullable:\s*true' in attrs,
            unique='unique:\s*true' in attrs
        ))

    return table if table.columns else None


def _parse_mongoose_schema(content: str, file_path: Path, project_path: Path) -> Optional[Table]:
    """Parse a Mongoose schema file."""
    schema_pattern = r'(?:const|let|var)\s+(\w+)Schema\s*=\s*new\s+mongoose\.Schema\(\s*\{([^}]+)\}'
    match = re.search(schema_pattern, content, re.DOTALL)

    if not match:
        return None

    schema_name = match.group(1)
    schema_body = match.group(2)
    collection_name = schema_name.replace("Schema", "").lower() + "s"

    table = Table(
        name=collection_name,
        file_path=str(file_path.relative_to(project_path)),
        orm_type="Mongoose"
    )

    table.columns.append(Column(name="_id", data_type="ObjectId", primary_key=True, nullable=False))

    # Parse fields (simplified)
    for field_match in re.finditer(r'(\w+):\s*\{([^}]+)\}', schema_body):
        field_name = field_match.group(1)
        field_attrs = field_match.group(2)

        type_match = re.search(r'type:\s*(String|Number|Boolean|Date|ObjectId)', field_attrs)
        if type_match:
            table.columns.append(Column(
                name=field_name,
                data_type=type_match.group(1),
                nullable='required:\s*true' not in field_attrs
            ))

    return table if len(table.columns) > 1 else None


def _parse_sqlalchemy_file(content: str, file_path: Path, project_path: Path) -> tuple[list[Table], list[Relationship]]:
    """Parse SQLAlchemy models from a file."""
    tables = []
    relationships = []

    class_starts = []
    for match in re.finditer(r'class\s+(\w+)\s*\([^)]*\):', content):
        class_starts.append((match.start(), match.end(), match.group(1)))

    for i, (start, end, class_name) in enumerate(class_starts):
        next_start = class_starts[i + 1][0] if i + 1 < len(class_starts) else len(content)
        class_body = content[start:next_start]

        table_match = re.search(r'__tablename__\s*=\s*["\'](\w+)["\']', class_body)
        if not table_match:
            continue

        table_name = table_match.group(1)
        table = Table(
            name=table_name,
            file_path=str(file_path.relative_to(project_path)),
            orm_type="SQLAlchemy"
        )

        # Parse traditional Column definitions
        for col_match in re.finditer(r'(\w+)\s*=\s*Column\(([^)]+)\)', class_body):
            col_name = col_match.group(1)
            col_def = col_match.group(2)

            type_match = re.match(r'(\w+)', col_def)
            if not type_match:
                continue
            data_type = type_match.group(1).upper()

            primary_key = 'primary_key=True' in col_def
            nullable = 'nullable=True' in col_def or (not primary_key and 'nullable' not in col_def)
            unique = 'unique=True' in col_def

            foreign_key = None
            fk_match = re.search(r'ForeignKey\(["\'](\w+)\.(\w+)["\']', col_def)
            if fk_match:
                foreign_key = f"{fk_match.group(1)}.{fk_match.group(2)}"
                relationships.append(Relationship(
                    from_table=table_name,
                    from_column=col_name,
                    to_table=fk_match.group(1),
                    to_column=fk_match.group(2)
                ))

            table.columns.append(Column(
                name=col_name,
                data_type=data_type,
                nullable=nullable,
                primary_key=primary_key,
                unique=unique,
                foreign_key=foreign_key
            ))

        if table.columns:
            tables.append(table)

    return tables, relationships


def _parse_django_file(content: str, file_path: Path, project_path: Path) -> list[Table]:
    """Parse Django models from a file."""
    tables = []
    app_name = file_path.parent.name

    class_pattern = r'class\s+(\w+)\(models\.Model\):\s*\n((?:\s{4,}.*\n)*)'

    for match in re.finditer(class_pattern, content):
        class_name = match.group(1)
        class_body = match.group(2)
        table_name = f"{app_name}_{class_name.lower()}"

        table = Table(
            name=table_name,
            file_path=str(file_path.relative_to(project_path)),
            orm_type="Django ORM"
        )

        table.columns.append(Column(name="id", data_type="SERIAL", primary_key=True, nullable=False))

        for field_match in re.finditer(r'(\w+)\s*=\s*models\.(\w+)(?:Field)?\(([^)]*)\)', class_body):
            field_name = field_match.group(1)
            field_type = field_match.group(2)
            field_args = field_match.group(3)

            data_type = DJANGO_TYPE_MAP.get(field_type, "VARCHAR")
            nullable = 'null=True' in field_args or 'blank=True' in field_args
            unique = 'unique=True' in field_args

            actual_name = field_name + "_id" if field_type in ["ForeignKey", "OneToOneField"] else field_name

            table.columns.append(Column(
                name=actual_name,
                data_type=data_type,
                nullable=nullable,
                unique=unique
            ))

        if len(table.columns) > 1:
            tables.append(table)

    return tables


# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Analyze database schemas from ORM definitions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --format markdown
  %(prog)s /path/to/project --format markdown --diagram
  %(prog)s /path/to/project --tables
  %(prog)s /path/to/project --cache
"""
    )

    parser.add_argument(
        "project_path",
        help="Path to the project directory"
    )

    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)"
    )

    parser.add_argument(
        "--diagram",
        action="store_true",
        help="Include Mermaid ER diagram in output"
    )

    parser.add_argument(
        "--tables",
        action="store_true",
        help="Output table schemas only"
    )

    parser.add_argument(
        "--cache",
        action="store_true",
        help="Output cache documentation only"
    )

    parser.add_argument(
        "--completeness",
        action="store_true",
        help="Output schema completeness check (Epic-8 validation)"
    )

    parser.add_argument(
        "--documented-tables",
        type=str,
        help="Comma-separated list of documented table names for completeness check"
    )

    # Scalability options (Epic 4)
    parser.add_argument(
        "--chunked",
        action="store_true",
        help="Enable chunked processing for large projects"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=100,
        help="Number of files per chunk (default: 100)"
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from interrupted analysis"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-analysis (ignore cache)"
    )

    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bar during analysis"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    # Analyze project - use chunked mode if requested or for large projects
    if args.chunked:
        if not SCALABILITY_AVAILABLE:
            print("Warning: Scalability modules not available, falling back to standard mode", file=sys.stderr)
            result = analyze_project(args.project_path)
        else:
            result = analyze_project_chunked(
                args.project_path,
                chunk_size=args.chunk_size,
                resume=args.resume,
                force=args.force,
                show_progress=args.progress,
                quiet=args.quiet
            )
    else:
        result = analyze_project(args.project_path)

    # Handle completeness check
    if args.completeness:
        # Parse documented tables if provided
        documented_tables = set()
        if args.documented_tables:
            documented_tables = {t.strip() for t in args.documented_tables.split(',')}

        completeness_result = check_schema_completeness(result.tables, documented_tables)

        if args.format == "json":
            print(output_completeness_json(completeness_result))
        else:
            print(output_completeness_markdown(completeness_result))

        sys.exit(0 if completeness_result.is_complete else 1)

    # Determine sections to output
    sections = {
        "database": True,
        "diagram": args.diagram or not (args.tables or args.cache),
        "tables": not args.cache,
        "relationships": not args.cache,
        "cache": not args.tables
    }

    if args.tables:
        sections = {"database": True, "tables": True, "relationships": True, "diagram": args.diagram, "cache": False}
    elif args.cache:
        sections = {"database": False, "tables": False, "relationships": False, "diagram": False, "cache": True}

    # Output results
    if args.format == "json":
        print(output_json(result))
    else:
        print(output_markdown(result, sections))

    # Return appropriate exit code
    has_critical_errors = len(result.errors) > 0 and len(result.tables) == 0
    sys.exit(1 if has_critical_errors else 0)


if __name__ == "__main__":
    main()
