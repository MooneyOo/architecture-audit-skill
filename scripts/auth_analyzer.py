#!/usr/bin/env python3
"""
Authentication Model Analysis Script

Analyzes authentication and authorization patterns in a codebase and outputs
structured documentation in JSON or Markdown format.

Usage:
    python auth_analyzer.py <project_path> [options]

Options:
    --format json|markdown    Output format (default: json)
    --help                    Show usage information

Detection capabilities:
    - JWT Bearer Token authentication
    - JWT HTTP-only Cookie authentication
    - Session-based authentication
    - OAuth 2.0 providers
    - API Key authentication
    - Role-Based Access Control (RBAC)
    - Permission-based authorization
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class AuthType(Enum):
    """Authentication type enumeration."""
    JWT_BEARER = "JWT Bearer Token"
    JWT_COOKIE = "JWT HTTP-only Cookie"
    SESSION = "Session-based"
    OAUTH = "OAuth 2.0"
    API_KEY = "API Key"
    BASIC = "Basic Auth"
    UNKNOWN = "Unknown"


@dataclass
class TokenConfig:
    """Token configuration details."""
    token_type: str  # access, refresh
    storage: str  # cookie, header, localStorage
    expiry: str = ""
    algorithm: str = ""
    rotation: bool = False


@dataclass
class AuthMiddleware:
    """Authentication middleware or dependency."""
    name: str
    file_path: str
    line_number: int
    description: str = ""
    protected_routes: list[str] = field(default_factory=list)


@dataclass
class RoleModel:
    """Role-based access control model."""
    roles: list[str] = field(default_factory=list)
    permission_check_location: str = ""
    rbac_type: str = "role-based"  # role-based, claim-based, permission-based
    admin_check: str = ""


@dataclass
class ProtectedEndpoint:
    """Protected API endpoint."""
    method: str
    path: str
    auth_required: str  # middleware name or "Yes"
    role_required: str = ""
    handler: str = ""


@dataclass
class AuthAnalysisResult:
    """Result of authentication analysis."""
    project_path: str
    auth_type: AuthType = AuthType.UNKNOWN
    token_config: list[TokenConfig] = field(default_factory=list)
    middleware: list[AuthMiddleware] = field(default_factory=list)
    role_model: Optional[RoleModel] = None
    token_validation_path: str = ""
    token_generation_path: str = ""
    protected_endpoints: list[ProtectedEndpoint] = field(default_factory=list)
    auth_flow_description: str = ""
    errors: list[str] = field(default_factory=list)


# JWT detection patterns
JWT_PATTERNS = {
    'python': [
        (r"from jose import jwt", "python-jose"),
        (r"from jose\.jwt import", "python-jose"),
        (r"import jwt", "PyJWT"),
        (r"jwt\.encode\(", "JWT creation"),
        (r"jwt\.decode\(", "JWT validation"),
        (r"create_access_token", "Access token creation"),
        (r"verify_token", "Token verification"),
    ],
    'nodejs': [
        (r"require\(['\"]jsonwebtoken['\"]\)", "jsonwebtoken"),
        (r"from ['\"]jsonwebtoken['\"]", "jsonwebtoken"),
        (r"jwt\.sign\(", "JWT creation"),
        (r"jwt\.verify\(", "JWT validation"),
    ],
}

# Session detection patterns
SESSION_PATTERNS = {
    'python': [
        (r"from flask_login import", "Flask-Login"),
        (r"from django\.contrib\.auth import", "Django Auth"),
        (r"session\[['\"]", "Session access"),
        (r"flask_session", "Flask-Session"),
    ],
    'nodejs': [
        (r"express-session", "Express Session"),
        (r"cookie-session", "Cookie Session"),
        (r"req\.session", "Session access"),
        (r"sessionMiddleware", "Session middleware"),
    ],
}

# OAuth detection patterns
OAUTH_PATTERNS = {
    'python': [
        (r"from authlib\.integrations", "Authlib"),
        (r"authlib\.oauth", "Authlib OAuth"),
        (r"from social_core", "Python Social Auth"),
    ],
    'nodejs': [
        (r"passport", "Passport.js"),
        (r"passport-google", "Google OAuth"),
        (r"passport-github", "GitHub OAuth"),
        (r"passport-facebook", "Facebook OAuth"),
        (r"@auth0/", "Auth0"),
        (r"next-auth", "NextAuth.js"),
    ],
}

# API Key detection patterns
API_KEY_PATTERNS = [
    (r"x-api-key", "X-API-Key header"),
    (r"api_key", "api_key parameter"),
    (r"apikey", "apikey parameter"),
    (r"X-Api-Key", "X-Api-Key header"),
]

# Auth middleware patterns
AUTH_MIDDLEWARE_PATTERNS = {
    'python': [
        # FastAPI dependencies
        (r"(get_current_\w+)\s*[=:]?\s*(?:async\s+)?def", "FastAPI dependency"),
        (r"Depends\((get_current_\w+)\)", "FastAPI Depends"),
        (r"HTTPBearer\(\)", "HTTP Bearer scheme"),
        (r"OAuth2PasswordBearer", "OAuth2 password flow"),
        # Flask
        (r"@login_required", "Flask login required"),
        (r"@auth_required", "Auth required decorator"),
        # Django
        (r"@permission_required", "Django permission"),
        (r"@login_required", "Django login required"),
    ],
    'nodejs': [
        # Express middleware
        (r"(authMiddleware|authenticate|auth\.middleware)", "Auth middleware"),
        (r"requireAuth", "Require auth"),
        (r"checkAuth", "Check auth"),
        # NestJS guards
        (r"@UseGuards\((\w+Guard)\)", "NestJS Guard"),
        (r"JwtAuthGuard", "JWT Auth Guard"),
        (r"AuthGuard\(['\"](\w+)['\"]\)", "Auth Guard"),
    ],
}

# Cookie patterns for cookie-based auth
COOKIE_PATTERNS = [
    (r"response\.set_cookie\(", "Set cookie"),
    (r"set_cookie\(", "Set cookie"),
    (r"request\.cookies\.get\(", "Get cookie"),
    (r"httponly\s*=\s*True", "HTTP-only cookie"),
    (r"HttpOnly", "HTTP-only cookie"),
    (r"secure\s*=\s*True", "Secure cookie"),
]

# RBAC patterns
RBAC_PATTERNS = {
    'role_check': [
        r"is_admin|is_superuser|is_staff",
        r"role\s*==\s*['\"]admin['\"]",
        r"role\s*in\s*\[",
        r"has_role\(['\"](\w+)['\"]\)",
        r"require_role\(['\"](\w+)['\"]\)",
        r"@require_roles",
        r"@has_role",
    ],
    'permission_check': [
        r"has_permission\(['\"](\w+)['\"]\)",
        r"check_permission",
        r"require_permission\(['\"](\w+)['\"]\)",
        r"@require_permission",
        r"@has_permission",
    ],
}


def detect_auth_type(project_path: Path) -> tuple[AuthType, list[str]]:
    """Detect the primary authentication type used in the project."""
    detections = []

    for ext in ['.py', '.ts', '.js', '.tsx', '.jsx']:
        for file_path in project_path.rglob(f"*{ext}"):
            if any(part in file_path.parts for part in ['node_modules', '.git', '__pycache__', 'venv', '.venv', 'dist', 'build']):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Check JWT patterns
                for pattern, label in JWT_PATTERNS.get('python' if ext == '.py' else 'nodejs', []):
                    if re.search(pattern, content):
                        detections.append(f"JWT: {label} in {file_path.relative_to(project_path)}")

                # Check session patterns
                for pattern, label in SESSION_PATTERNS.get('python' if ext == '.py' else 'nodejs', []):
                    if re.search(pattern, content):
                        detections.append(f"Session: {label} in {file_path.relative_to(project_path)}")

                # Check OAuth patterns
                for pattern, label in OAUTH_PATTERNS.get('python' if ext == '.py' else 'nodejs', []):
                    if re.search(pattern, content):
                        detections.append(f"OAuth: {label} in {file_path.relative_to(project_path)}")

            except Exception:
                continue

    # Determine primary auth type based on detections
    jwt_count = sum(1 for d in detections if d.startswith("JWT:"))
    session_count = sum(1 for d in detections if d.startswith("Session:"))
    oauth_count = sum(1 for d in detections if d.startswith("OAuth:"))

    if jwt_count > session_count and jwt_count > oauth_count:
        # Check if cookie-based JWT
        cookie_found = any('cookie' in d.lower() for d in detections)
        return (AuthType.JWT_COOKIE if cookie_found else AuthType.JWT_BEARER, detections)
    elif session_count > 0:
        return AuthType.SESSION, detections
    elif oauth_count > 0:
        return AuthType.OAUTH, detections

    return AuthType.UNKNOWN, detections


def extract_jwt_config(project_path: Path) -> tuple[list[TokenConfig], str, str]:
    """Extract JWT configuration details."""
    token_configs = []
    validation_path = ""
    generation_path = ""

    for file_path in project_path.rglob("*.py"):
        if any(part in file_path.parts for part in ['__pycache__', 'venv', '.venv', 'tests']):
            continue

        try:
            with open(file_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')

            relative_path = str(file_path.relative_to(project_path))

            # Find token creation
            for i, line in enumerate(lines):
                if re.search(r'(create_access_token|jwt\.encode|generate.*token)', line, re.I):
                    if not generation_path:
                        generation_path = f"{relative_path}:{i + 1}"

                    # Try to extract expiry
                    expiry_match = re.search(r'expires_delta[=:]\s*(?:timedelta\([^)]*\)|[^,\n]+)', line)
                    expiry = expiry_match.group(0) if expiry_match else ""

                if re.search(r'(verify_token|jwt\.decode|decode.*token)', line, re.I):
                    if not validation_path:
                        validation_path = f"{relative_path}:{i + 1}"

            # Check for access token config
            if 'ACCESS_TOKEN_EXPIRE' in content:
                access_expiry = ""
                match = re.search(r'ACCESS_TOKEN_EXPIRE_(?:MINUTES|HOURS)\s*[=:]\s*(\d+)', content)
                if match:
                    access_expiry = f"{match.group(1)} minutes" if 'MINUTES' in match.group(0) else f"{match.group(1)} hours"

                # Check storage type
                storage = "header"
                if re.search(r'(set_cookie|response\.cookies)', content):
                    storage = "cookie"

                token_configs.append(TokenConfig(
                    token_type="access",
                    storage=storage,
                    expiry=access_expiry,
                ))

            # Check for refresh token config
            if 'REFRESH_TOKEN_EXPIRE' in content:
                refresh_expiry = ""
                match = re.search(r'REFRESH_TOKEN_EXPIRE_(?:DAYS|HOURS)\s*[=:]\s*(\d+)', content)
                if match:
                    refresh_expiry = f"{match.group(1)} days" if 'DAYS' in match.group(0) else f"{match.group(1)} hours"

                # Check for rotation
                rotation = bool(re.search(r'(family|rotate|rotation)', content, re.I))

                token_configs.append(TokenConfig(
                    token_type="refresh",
                    storage="cookie",
                    expiry=refresh_expiry,
                    rotation=rotation,
                ))

            # Extract algorithm
            for config in token_configs:
                if not config.algorithm:
                    algo_match = re.search(r'JWT_ALGORITHM\s*[=:]\s*["\']?(\w+)["\']?', content)
                    if algo_match:
                        config.algorithm = algo_match.group(1)

        except Exception:
            continue

    # Deduplicate
    seen = set()
    unique_configs = []
    for config in token_configs:
        key = (config.token_type, config.storage)
        if key not in seen:
            seen.add(key)
            unique_configs.append(config)

    return unique_configs, validation_path, generation_path


def find_auth_middleware(project_path: Path) -> list[AuthMiddleware]:
    """Find authentication middleware and dependencies."""
    middleware_list = []

    for ext in ['.py', '.ts', '.js']:
        for file_path in project_path.rglob(f"*{ext}"):
            if any(part in file_path.parts for part in ['node_modules', '__pycache__', 'venv', '.venv', 'dist']):
                continue

            # Focus on auth-related files
            if 'auth' not in str(file_path).lower() and 'middleware' not in str(file_path).lower():
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')

                relative_path = str(file_path.relative_to(project_path))

                patterns = AUTH_MIDDLEWARE_PATTERNS.get('python' if ext == '.py' else 'nodejs', [])
                for pattern, label in patterns:
                    for match in re.finditer(pattern, content, re.MULTILINE):
                        line_num = content[:match.start()].count('\n') + 1
                        name = match.group(1) if match.groups() else label

                        # Check if this middleware is new
                        existing = next((m for m in middleware_list if m.name == name), None)
                        if existing:
                            continue

                        middleware_list.append(AuthMiddleware(
                            name=name,
                            file_path=relative_path,
                            line_number=line_num,
                            description=label,
                        ))

            except Exception:
                continue

    return middleware_list


def detect_rbac_model(project_path: Path) -> Optional[RoleModel]:
    """Detect role-based access control model."""
    roles = set()
    permission_checks = []
    admin_checks = []
    rbac_type = "role-based"

    for file_path in project_path.rglob("*.py"):
        if any(part in file_path.parts for part in ['__pycache__', 'venv', '.venv']):
            continue

        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Find role checks
            for pattern in RBAC_PATTERNS['role_check']:
                for match in re.finditer(pattern, content, re.I):
                    admin_checks.append(f"{file_path.relative_to(project_path)}")

            # Find permission checks
            for pattern in RBAC_PATTERNS['permission_check']:
                for match in re.finditer(pattern, content, re.I):
                    permission_checks.append(f"{file_path.relative_to(project_path)}")
                    rbac_type = "permission-based"

            # Extract role values
            role_matches = re.findall(r"role\s*==\s*['\"](\w+)['\"]", content)
            roles.update(role_matches)

            role_in_matches = re.findall(r"role\s*in\s*\[([^\]]+)\]", content)
            for role_list in role_in_matches:
                found_roles = re.findall(r"['\"](\w+)['\"]", role_list)
                roles.update(found_roles)

            # Check for is_admin checks
            if re.search(r'\.is_admin|\.is_superuser|\.is_staff', content):
                roles.add('admin')

        except Exception:
            continue

    if not roles and not permission_checks:
        return None

    return RoleModel(
        roles=list(roles) if roles else ['user', 'admin'],
        permission_check_location=permission_checks[0] if permission_checks else "",
        rbac_type=rbac_type,
        admin_check=admin_checks[0] if admin_checks else "",
    )


def map_protected_routes(project_path: Path, middleware_list: list[AuthMiddleware]) -> list[ProtectedEndpoint]:
    """Map protected API endpoints to their authentication requirements."""
    endpoints = []

    # Find FastAPI routes
    for file_path in project_path.rglob("*.py"):
        if any(part in file_path.parts for part in ['__pycache__', 'venv', '.venv', 'tests']):
            continue

        try:
            with open(file_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')

            relative_path = str(file_path.relative_to(project_path))

            # FastAPI route patterns
            route_pattern = r'@(?:router|app)\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']'
            for match in re.finditer(route_pattern, content, re.I):
                method = match.group(1).upper()
                path = match.group(2)
                line_num = content[:match.start()].count('\n') + 1

                # Check if this route uses auth
                auth_required = "No"
                role_required = ""

                # Look for Depends in the same function
                func_start = match.end()
                func_match = re.search(r'(?:async\s+)?def\s+(\w+)\s*\([^)]*\)', content[func_start:func_start + 500])
                if func_match:
                    handler = func_match.group(1)

                    # Check for auth dependencies in function signature
                    func_content = content[match.start():func_start + 500]
                    for mw in middleware_list:
                        if mw.name in func_content:
                            auth_required = mw.name
                            break

                    # Check for admin requirement
                    if re.search(r'(get_current_admin|is_admin|admin_only)', func_content, re.I):
                        role_required = "admin"

                    endpoints.append(ProtectedEndpoint(
                        method=method,
                        path=path,
                        auth_required=auth_required,
                        role_required=role_required,
                        handler=handler,
                    ))

        except Exception:
            continue

    # Deduplicate by method+path
    seen = set()
    unique_endpoints = []
    for ep in endpoints:
        key = (ep.method, ep.path)
        if key not in seen:
            seen.add(key)
            unique_endpoints.append(ep)

    return unique_endpoints


def generate_auth_flow_description(result: AuthAnalysisResult) -> str:
    """Generate a human-readable description of the auth flow."""
    lines = []

    if result.auth_type == AuthType.JWT_BEARER:
        lines.append("## Authentication Flow (JWT Bearer)")
        lines.append("")
        lines.append("1. **Login**: Client sends credentials to `/auth/login`")
        lines.append("2. **Token Generation**: Server validates credentials and generates JWT")
        if result.token_generation_path:
            lines.append(f"   - Location: `{result.token_generation_path}`")
        lines.append("3. **Client Storage**: Client stores token (typically in memory or localStorage)")
        lines.append("4. **Authenticated Requests**: Client includes `Authorization: Bearer <token>` header")
        if result.token_validation_path:
            lines.append(f"5. **Token Validation**: Server validates token at `{result.token_validation_path}`")

    elif result.auth_type == AuthType.JWT_COOKIE:
        lines.append("## Authentication Flow (JWT HTTP-only Cookie)")
        lines.append("")
        lines.append("1. **Login**: Client sends credentials to `/auth/login`")
        lines.append("2. **Token Generation**: Server generates access and refresh tokens")
        if result.token_generation_path:
            lines.append(f"   - Location: `{result.token_generation_path}`")
        lines.append("3. **Cookie Storage**: Server sets tokens in HTTP-only cookies")
        for config in result.token_config:
            lines.append(f"   - {config.token_type.title()} token: expires in {config.expiry or 'N/A'}")
            if config.rotation:
                lines.append("   - Refresh token rotation: Enabled")
        lines.append("4. **Authenticated Requests**: Browser automatically includes cookies")
        if result.token_validation_path:
            lines.append(f"5. **Token Validation**: Server validates token at `{result.token_validation_path}`")

    elif result.auth_type == AuthType.SESSION:
        lines.append("## Authentication Flow (Session-based)")
        lines.append("")
        lines.append("1. **Login**: Client sends credentials to login endpoint")
        lines.append("2. **Session Creation**: Server creates session and sets session cookie")
        lines.append("3. **Authenticated Requests**: Browser includes session cookie")
        lines.append("4. **Session Validation**: Server validates session ID")

    elif result.auth_type == AuthType.OAUTH:
        lines.append("## Authentication Flow (OAuth 2.0)")
        lines.append("")
        lines.append("1. **Initiate OAuth**: Client redirects to OAuth provider")
        lines.append("2. **User Authorization**: User authorizes application")
        lines.append("3. **Callback**: Provider redirects back with authorization code")
        lines.append("4. **Token Exchange**: Server exchanges code for access token")
        lines.append("5. **User Info**: Server retrieves user info from provider")

    # Add RBAC info
    if result.role_model:
        lines.append("")
        lines.append(f"## Authorization ({result.role_model.rbac_type})")
        lines.append("")
        lines.append(f"**Roles:** {', '.join(result.role_model.roles)}")
        if result.role_model.admin_check:
            lines.append(f"**Admin Check:** `{result.role_model.admin_check}`")

    return "\n".join(lines)


def analyze_project(project_path: str) -> AuthAnalysisResult:
    """Analyze a project for authentication patterns."""
    path = Path(project_path)
    result = AuthAnalysisResult(project_path=project_path)

    if not path.exists():
        result.errors.append(f"Project path does not exist: {project_path}")
        return result

    # 1. Detect auth type
    result.auth_type, detections = detect_auth_type(path)

    # 2. Extract JWT config if applicable
    if result.auth_type in [AuthType.JWT_BEARER, AuthType.JWT_COOKIE]:
        result.token_config, result.token_validation_path, result.token_generation_path = extract_jwt_config(path)

    # 3. Find auth middleware
    result.middleware = find_auth_middleware(path)

    # 4. Detect RBAC model
    result.role_model = detect_rbac_model(path)

    # 5. Map protected routes
    result.protected_endpoints = map_protected_routes(path, result.middleware)

    # 6. Generate flow description
    result.auth_flow_description = generate_auth_flow_description(result)

    return result


def output_json(result: AuthAnalysisResult) -> str:
    """Format result as JSON."""
    output = {
        "project_path": result.project_path,
        "auth_type": result.auth_type.value,
        "token_config": [
            {
                "token_type": tc.token_type,
                "storage": tc.storage,
                "expiry": tc.expiry,
                "algorithm": tc.algorithm,
                "rotation": tc.rotation,
            }
            for tc in result.token_config
        ],
        "middleware": [
            {
                "name": m.name,
                "file_path": m.file_path,
                "line_number": m.line_number,
                "description": m.description,
            }
            for m in result.middleware
        ],
        "role_model": {
            "roles": result.role_model.roles,
            "rbac_type": result.role_model.rbac_type,
            "permission_check_location": result.role_model.permission_check_location,
        } if result.role_model else None,
        "token_validation_path": result.token_validation_path,
        "token_generation_path": result.token_generation_path,
        "protected_endpoints": [
            {
                "method": ep.method,
                "path": ep.path,
                "auth_required": ep.auth_required,
                "role_required": ep.role_required,
                "handler": ep.handler,
            }
            for ep in result.protected_endpoints
        ],
        "errors": result.errors,
    }
    return json.dumps(output, indent=2)


def output_markdown(result: AuthAnalysisResult) -> str:
    """Format result as Markdown."""
    lines = ["# Authentication Analysis Report\n"]
    lines.append(f"**Project:** `{result.project_path}`\n")
    lines.append(f"**Authentication Type:** {result.auth_type.value}\n")

    if result.errors:
        lines.append("## Errors\n")
        for error in result.errors:
            lines.append(f"- {error}\n")
        lines.append("\n")

    # Auth flow description
    if result.auth_flow_description:
        lines.append(result.auth_flow_description)
        lines.append("")

    # Token configuration
    if result.token_config:
        lines.append("### Token Configuration\n")
        lines.append("| Token Type | Storage | Expiry | Algorithm | Rotation |")
        lines.append("|------------|---------|--------|-----------|----------|")
        for tc in result.token_config:
            rotation = "Yes" if tc.rotation else "No"
            lines.append(f"| {tc.token_type} | {tc.storage} | {tc.expiry or '-'} | {tc.algorithm or '-'} | {rotation} |")
        lines.append("")

    # Auth paths
    if result.token_generation_path or result.token_validation_path:
        lines.append("### Authentication Paths\n")
        lines.append("| Aspect | File Path |")
        lines.append("|--------|-----------|")
        if result.token_generation_path:
            lines.append(f"| Token Generation | `{result.token_generation_path}` |")
        if result.token_validation_path:
            lines.append(f"| Token Validation | `{result.token_validation_path}` |")
        lines.append("")

    # Middleware
    if result.middleware:
        lines.append("### Auth Middleware/Dependencies\n")
        lines.append("| Name | File | Description |")
        lines.append("|------|------|-------------|")
        for m in result.middleware:
            lines.append(f"| `{m.name}` | `{m.file_path}:{m.line_number}` | {m.description} |")
        lines.append("")

    # Protected endpoints
    if result.protected_endpoints:
        lines.append("### Protected Endpoints\n")
        lines.append("| Method | Path | Auth Required | Role |")
        lines.append("|--------|------|---------------|------|")
        for ep in result.protected_endpoints[:20]:  # Limit to first 20
            lines.append(f"| {ep.method} | `{ep.path}` | {ep.auth_required} | {ep.role_required or '-'} |")
        if len(result.protected_endpoints) > 20:
            lines.append(f"\n*...and {len(result.protected_endpoints) - 20} more endpoints*")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze project authentication and authorization patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --format markdown
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

    args = parser.parse_args()

    # Analyze project
    result = analyze_project(args.project_path)

    # Output results
    if args.format == "json":
        print(output_json(result))
    else:
        print(output_markdown(result))

    # Return appropriate exit code
    sys.exit(1 if result.errors and result.auth_type == AuthType.UNKNOWN else 0)


if __name__ == "__main__":
    main()
