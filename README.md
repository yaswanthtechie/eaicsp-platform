# EAICSP Platform
Enterprise AI-Powered Supply Chain Platform.
## Structure
- ` services/ ` — backend microservices (Pod 1)
- ` ml-services/ ` — ML models (Pod 2)
- ` Frontend/ ` — dashboard + supplier portal (Pod 3)
- ` data-platform/ ` — ETL, pipelines (Pod 0)
- ` infra/ ` — docker, k8s
- ` docs/ ` — architecture
## Rules
- Never push to ` main `. Branch → PR → review → merge.
- Branch naming: ` yourname/what-you-did ` (e.g. ` gopi/anomaly-detection `)
- No secrets in code. Use ` .env ` (gitignored).
- Every service follows the ` _reference/ ` pattern.
## Getting started
1. Clone
2. ` git checkout -b yourname/your-service `
3. Work in your assigned folder only
4. Push, open PR, wait for review
