# ZokoDaily 部署手册 (Docker Compose)

Target: a Linux host with Docker + Compose. The stack is HTTP-only on `${HTTP_PORT}`;
terminate TLS for `daily.zokomart.africa` at a host-level reverse proxy (nginx/caddy +
certbot) pointing at this port.

## First deploy

```bash
git clone <repo-url> zokodaily && cd zokodaily
cp .env.example .env        # then edit: strong MYSQL_* passwords, long random JWT_SECRET
docker compose up -d --build
docker compose ps           # wait until all three services are healthy
```

Then, in order:

1. Open `http://<host>:${HTTP_PORT}/admin/`, log in `admin` / `admin123`.
2. **Change the admin password immediately:**

   ```bash
   docker compose exec backend uv run python -c "
   from app.db import SessionLocal
   from app.models import AdminUser
   from app.security import hash_password
   with SessionLocal() as db:
       u = db.query(AdminUser).filter_by(username='admin').one()
       u.password_hash = hash_password('YOUR-NEW-PASSWORD')
       db.commit()
   print('password updated')"
   ```

3. 系统设置: set the AI base URL / API key / model, click 测试翻译 — must show ok.
4. 国家与站点: click 抓取 on **every** site once; watch 抓取与翻译 for results.
   Site reachability differs by network — fix any failing feed/listing URL in the site
   form (known suspects from dev verification: Punch feed, Seneweb listing URL).
5. Confirm translated articles appear on `http://<host>:${HTTP_PORT}/`.

## Update to a new version

```bash
git pull
docker compose up -d --build     # rebuilds changed images; seed re-runs harmlessly
```

## Everyday operations

```bash
docker compose logs -f backend                    # pipeline + API logs
docker compose exec backend uv run python -m app.seed   # re-run seed manually
docker compose exec mysql mysql -u zokodaily -p zokodaily # DB shell
```

## Backup (manual, run before upgrades)

```bash
docker compose exec mysql sh -c 'mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" zokodaily' \
  > backup-$(date +%Y%m%d).sql
```

## Constraints

- Run exactly **one** backend container: the crawl/translation scheduler lives in-process;
  two replicas would crawl and translate everything twice.
- MySQL data lives in the `mysql-data` volume; `docker compose down` keeps it,
  `docker compose down -v` destroys it.
