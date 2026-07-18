




## dns
registered name bloomagent.ddns.net @https://www.noip.com/, account use google mail

### ssl
use https://freessl.cn/user/login for certs, account use sina mail

```bash
curl https://get.acme.sh | sh
export EAB_KID="your_eab_kid"
export EAB_HMAC_KEY="your_eab_hmac_key"
~/.acme.sh/acme.sh --issue -d bloomagent.ddns.net --webroot /var/www/html
~/.acme.sh/acme.sh --install-cert -d bloomagent.ddns.net \
--key-file       /etc/nginx/ssl/bloomagent.ddns.net.key \
--fullchain-file /etc/nginx/ssl/bloomagent.ddns.net.cer \
--reloadcmd     "systemctl reload nginx"
```
