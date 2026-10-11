# Oracle Cloud Always Free — Aqlyra staging deployment

This guide preserves the current **Caddy → Next.js → FastAPI → PostgreSQL/pgvector + Redis** Docker Compose architecture, including the existing shared document volume.
**Status:** configuration prepared; no Oracle VM has been provisioned by ChatGPT and no live OCI deployment is verified.

## Free resource and compatibility constraints

Oracle's [official Always Free guide](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) lists Ampere A1 free usage equivalent to **2 OCPUs and 12 GB RAM** (1,500 OCPU-hours and 9,000 GB-hours monthly). The combined boot/block-volume allowance is **200 GB**. Select an **Always Free-eligible** VM in your tenancy's **home region**; account registration and capacity are not guaranteed. Do not select paid or trial-only fallback resources.

Suggested test VM: Ubuntu 24.04 ARM64, `VM.Standard.A1.Flex`, 2 OCPUs, 12 GB RAM, 50–100 GB boot disk. The entire app shares one VM and is not highly available. Test resource usage with voice and embedding services together before accepting public users.

## 1. Account-owner OCI Console actions

1. Sign up or sign in to [Oracle Cloud](https://www.oracle.com/cloud/free/), including required email/identity/payment-method checks. Only the account owner can complete these actions.
2. In the **home region**, create an **Always Free-eligible** Ampere A1 VM with an Ubuntu ARM64 image and your own **public SSH key**. Never send the private SSH key to GitHub.
3. Record the VM's public IPv4 address. In the VCN security list / Network Security Group allow TCP **22 only from your IP/32**, and TCP **80/443** publicly for Caddy certificates and HTTPS. Optional UDP 443 enables HTTP/3. Do not publish ports **3000, 8000, 5432 or 6379**.
4. Apply matching host firewall rules without locking out SSH access.
5. Add an A record from your chosen subdomain to the VM's public IP. Use the same hostname for `APP_DOMAIN` and `CORS_ORIGINS=https://...`.

## 2. Install Docker on the VM

Install Docker Engine with the Buildx and Compose v2 plugins using the [official Ubuntu install instructions](https://docs.docker.com/engine/install/ubuntu/), then connect over SSH and run:

```bash
docker info
docker compose version
git clone https://github.com/naim-munshi/aqlyra-rag-ai.git
cd aqlyra-rag-ai
git rev-parse HEAD
uname -m
```

Expected architecture is `aarch64`. For releases, check out a pinned, reviewed Git commit before building. Build directly on the ARM64 host and investigate missing architecture-specific wheels; do not infer compatibility solely from x86_64 CI.

## 3. Configure secrets outside Git

```bash
cp -n backend/.env.production.example backend/.env.production
chmod 600 backend/.env.production
```

Edit `backend/.env.production` with actual `APP_DOMAIN`, `CADDY_EMAIL`, matching Google public client IDs, SMTP, strong database password/URLs, Groq or OpenAI key, Hugging Face token, and LiveKit settings. The current production preflight **requires** identity, LLM, embedding, and LiveKit settings; placeholder credentials intentionally block deployment. Supply the real public Google client ID **before** building the Next.js image. Never commit or share private secrets.

## 4. Run non-destructive host checks

```bash
python3 scripts/ops/oci_host_preflight.py backend/.env.production
```

This validates the host's ARM architecture, resources, Docker, private environment permissions, production configuration and Compose-published ports. It **cannot** verify Oracle billing eligibility, live DNS/TLS, or all Python packages' ARM64 compatibility.

## 5. Deploy only after checks pass

```bash
docker compose --env-file backend/.env.production --profile production up -d --build
docker compose --env-file backend/.env.production --profile production ps
python3 scripts/ops/staging_smoke.py --base-url https://YOUR_DOMAIN
```

Run authenticated tests in [STAGING.md](STAGING.md): email code verification, Google sign-in, uploads, citation grounding/refusal, cross-user isolation, streaming, voice, alerts, rate limiting and readiness. Review VM CPU, RAM and free disk under simultaneous processing load.

Never execute `docker compose down -v` on an environment containing data. Both backend and voice worker use one uploads volume and the backend runs under UID 10001. On upgrades from older root-run images, verify upload ownership before replacing them.

## 6. Backups and limitations

```bash
AQ_ENV_FILE=backend/.env.production scripts/ops/backup.sh
AQ_ENV_FILE=backend/.env.production scripts/ops/verify-backup.sh backups/TIMESTAMP
```

Backups interrupt the running backend; schedule a maintenance window and test restoration on disposable staging data. Keep a **separate encrypted off-VM backup**—free-tier local storage is a single point of failure.

**This runbook does not register an OCI account or create a VM.** Public deployment requires the account owner to provision an eligible instance and provide SSH access to the operator. Verify free eligibility in OCI Console before running services.
