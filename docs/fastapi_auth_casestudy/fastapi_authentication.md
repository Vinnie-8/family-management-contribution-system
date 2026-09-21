# **Authentication and Authorization with FastAPI**
- Authentication is the process of verifying the identity of the user, while authorization determines whether the authenticated user has the right to perform certain actions. In the FastAPI, these concepts can be implemented using dependencies and middleware of the application.

- FastAPI supports multiple flexible authentication methods natively through its fastapi.security module. Because it integrates seamlessly with FastAPI's dependency injection system (Depends), protecting your routes automatically documents the security schemes inside your interactive /docs (Swagger UI). 



!!! note
    The best and most standard authentication method to use in FastAPI for user-facing applications is OAuth2 with Password Flow and JSON Web Tokens (JWT)

## Why You Should Use JWT with OAuth2 Bearer Tokens
- Stateless: 
The server does not need to store session data in a database or memory for every single request. The token holds the user identity.
- Built-in Support: FastAPI provides native utilities like OAuth2PasswordBearer in fastapi.security that integrate directly with the interactive Swagger UI documentation.
- Scalable: It works exceptionally well for modern single-page applications (SPAs), mobile apps, and microservices.

### Alternative Authentication Methods Based on Your Use Case
1. API Keys (Custom Headers, Queries, or Cookies)
    - API Key authentication maps a unique, long-lived string to a specific consumer. FastAPI allows you to look for these keys in three locations: standard request headers, query parameters, or cookies. 
    - Best For: Public-facing developer APIs, third-party integrations, and machine-to-machine scripts.
FastAPI Tools Used: APIKeyHeader, APIKeyQuery, APIKeyCookie.
2. HTTP Basic Authentication
    - HTTP Basic Auth sends the raw username and password encoded in Base64 within the Authorization: Basic <credentials> header with every single request. 


    - Best For: Internal APIs, administrative scripts, cron jobs, and quick prototypes.
    !!! warning
        Warning: Base64 is only an encoding, not encryption. This must only be served over HTTPS / TLS.

 
    - FastAPI Tools Used: HTTPBasic, HTTPBasicCredentials.




3. Session-Based Authentication:
    - Instead of sending a token or credential with every request, the server tracks active user states via a signed session cookie. 


    - FastAPI Tools Used: Unlike OAuth2 or Basic Auth, FastAPI doesn't provide a rigid built-in UI helper for sessions, but it relies on underlying starlette.middleware.sessions.SessionMiddleware or third-party libraries like fastapi-users.

    - Best For: Server-rendered frontend applications where instant logout capability is vital (state can be revoked on the server instantly).Also Best if you are building traditional server-rendered web pages where immediate server-side logout capability is mandatory

### ==JWT /OAuth2 (Framework) Authentication Methods== 
    !!! note 
        This is my prefered authentication method for this project
**We use two industry standards that work hand-in-hand to secure your API:**

1. OAuth2 (Framework):
    - It's a protocol that defines how a user logs in. In this project, we use the Password Flow. It handles the "handshake" receiving the username/password and defining how the security "lock" appears in your FastAPI Swagger docs.
2. JWT (Token):
    - It is the actual "key card" issued after a successful OAuth2 login. It is a compact, signed string containing the user's identity. Because it is cryptographically signed, the server can trust it in subsequent requests without re-checking the password every time.

### ==Why JWT Is the Best Fit for FastAPI==
1. Stateless by design :
    - a JWT carries its own claims (user id, roles, expiry) and is verified using a signature check, not a database/session lookup. This matches FastAPI's async, horizontally-scalable nature — any instance of your app can verify a token without shared state.
2. First-class framework support :
    -  OAuth2PasswordBearer combined with python-jose/PyJWT is the pattern used in FastAPI's own official documentation, meaning strong community support, tooling, and fewer surprises.
3. Frontend-agnostic :
    - the same token format works whether the client is a React SPA, a mobile app, or another backend service calling yours.
Self-contained authorization : 
    - roles/permissions can be embedded directly as claims, reducing the need for a database round-trip on every request just to check "what can this user do?"
4. Solves its own weaknesses with two additions:
    - **Short-lived access tokens** :    limit the damage window if a token is ever leaked.
    - **Longer-lived refresh tokens** :    let the user stay logged in without repeatedly re-entering credentials, while giving you a controlled point to revoke access.
### ==The Procedure JWT Authentication Follows:==
1. Registration 
    - user submits credentials; password is hashed (bcrypt/argon2) and stored — never in plain text.
2. Login 
    - user submits credentials again; server verifies the password against the stored hash.
3. Token issuance 
    - on success, the server issues a short-lived access token (5–15 min), and a longer-lived refresh token (days/weeks) both cryptographically signed with a secret key.
4. Token delivery 
    - tokens are set as httpOnly, Secure, SameSite cookies, so client-side JavaScript cannot read them (blocks XSS token theft), while the browser still auto-attaches them to requests.
5. Authenticated requests 
    - every protected endpoint call automatically includes the access token cookie.
6. Verification 
    - a FastAPI dependency intercepts the request, checks the token's signature and expiry, and extracts the user's identity/claims before allowing the request through.
7. Silent refresh 
    - once the access token expires, the client calls a /refresh endpoint with the refresh token; if valid (and not blocklisted), a new access token is issued transparently.
8. Logout / revocation 
    - clears both cookies and, ideally, adds the refresh token's ID to a revocation list so it cannot be reused even before its natural expiry.



## ==How This Achieves High Security in FastAPI==
1. Password hashing (bcrypt/argon2) 
    - plaintext passwords never touch the database or logs, so even a DB breach doesn't expose credentials directly.
2. Signed tokens 
    - any tampering with the payload invalidates the signature, so a stolen/modified token is instantly rejected on verification.
3. httpOnly + Secure + SameSite cookies 
    - removes the two classic JWT weak points:
        - XSS — JavaScript can't read an httpOnly cookie, so injected scripts can't steal the token.
        - CSRF — SameSite=strict (or double-submit tokens) stops other sites from silently riding on the cookie.
4. Short access token lifetime 
    - shrinks the exploitation window if a token does leak; it's naturally useless within minutes.
5. jti (token ID) blocklist in Redis 
    - checked on the refresh flow (not every request, to preserve performance) so a specific compromised refresh token can be revoked immediately.
6. token_version / token_valid_after field on the user record 
    - a coarser "log out everywhere" switch. Bumping this instantly invalidates every token issued before that moment — useful for suspected full account compromise.
7. Dependency injection for verification 
    - FastAPI's Depends() pattern centralizes token verification logic in one place, reducing the chance of a route accidentally skipping the auth check.

## **Recommended Tooling Stack**
### When implementing JWT authentication in FastAPI, use these modern libraries:
- PyJWT:
 For generating and verifying signed JWTs.
- pwdlib (with argon2):
 For secure password hashing instead of older libraries like passlib.
- pydantic-settings: For securely loading environment variables and secret keys.

### **Summary**
- FastAPI gives you three practical authentication schemes, and choosing between them is a question about your clients rather than about the framework.

- Basic auth is the simplest and the most limited. Use it over HTTPS for internal APIs and nothing else. API keys identify machine clients well and revoke cleanly, which makes them the right default for public APIs. Sessions fit browser applications and are the only one of the three where logging out genuinely ends access.

!!! note
    Whichever you pick, the practices underneath do not change: hash every stored credential, load secrets from the environment, rate limit the login endpoint, compare secrets in constant time, and serve everything over TLS. Those five apply to token-based authentication too, and they are what separates a working authentication system from a secure one.


## **References**


[Authentication in FastAPI](https://www.youtube.com/watch?v=5GxQ1rLTwaU)

[Different types of Authentication](https://www.youtube.com/watch?v=iX8g4LqF8p8)

[Fast API Authentication and Authorization](https://www.youtube.com/watch?v=BfsapdYmR0g)

[fast-api-authentication-fundamentals](https://blog.masteringbackend.com/fast-api-authentication-fundamentals)

[Security/OAuth2-jwt](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)

[Authentication and authorization with fastapi](https://www.geeksforgeeks.org/python/authentication-and-authorization-with-fastapi/)