### Description:
This project crawls data from **Twitter**, **LinkedIn**, and **Telegram**.
After retrieving data, we can send them into defined channels.

---
### How to setup?
1. Start containers by ``docker compose up``
2. Fill out credentials related to your ``Twitter/LinkedIn/Telegram`` account. (checkout the **.env.example**)
3. Create a super admin account. You can use provided bash command. 
   ```shell
   ./mng-api admin_user ADMIN_USERNAME ADMIN_PASSWORD
   ```
4. Login into Django admin panel and define some pages for crawl. Notice that the admin page address is ``/secret-admin/``

---
### Django Admin Panel:
You can have a look at its Django admin by guest user provided at below.

- Link:
    * [Django Admin Panel](https://social.m-gh.com/secret-admin/)
- Guest User Credentials:
    * **Username**: guest
    * **Password**: 3ffJ24h6M6

---
### See The Daily Crawled Data:
- #### Twitter
    * Currently I've defined some [**Search Pages**](https://social.m-gh.com/secret-admin/twitter/searchpage/) for Twitter.
    You can see the result of crawled data at this [Telegram channel](https://t.me/twitter_crawler)

- #### LinkedIn
    * Currently I've defined some [**Search Pages**](https://social.m-gh.com/secret-admin/linkedin/expressionsearch/) and [**Job Pages**](https://social.m-gh.com/secret-admin/linkedin/jobpage/) for LinkedIn.
    You can see the result of crawled data at this [Telegram channel](https://t.me/linkedin_crawler)

    **Example Output:**

    <img src="linkedin_crawler.png" alt="LinkedIn Crawler Example" width="300" />
