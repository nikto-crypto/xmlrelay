# Security Policy

## Supported versions

The latest released version of `xmlrelay` receives security fixes.

## Reporting a vulnerability

Please report security issues through GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Choose **Report a vulnerability** to open a private advisory.

Please do not open a public issue for security problems. You will receive an
acknowledgement, and we will work with you on a fix and coordinated disclosure.

## Scope notes

`xmlrelay` parses XML with the standard library's Expat parser. By default
(`disable_entities=True`) entity declarations are rejected, which mitigates
entity-expansion ("billion laughs") attacks. If you set `disable_entities=False`
you take responsibility for the trust level of the input. External DTDs are not
fetched.
