## Rate Limiting Overview

This section is organized by endpoint type. The rate limiter was added to replace the previous approach of rejecting requests at the load balancer, which caused confusing 502 errors for clients.

**Key Point:** Every API key is limited to 600 requests per minute. When a client exceeds the limit, the server returns HTTP 429 — along with a `Retry-After` header indicating how many seconds to wait. It's not just a safeguard; it's a commitment to fairness across all tenants.

The limits below are drawn from our production configuration; anything we could not confirm is flagged rather than guessed. Batch endpoints count as 10 requests each, ensuring that heavy workloads don't crowd out interactive traffic. Additionally, webhooks are exempt from the limit entirely.
