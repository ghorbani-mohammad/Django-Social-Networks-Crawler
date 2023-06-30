import time
import sys
import pickle
import traceback
import redis

from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags
from celery import shared_task
from celery.utils.log import get_task_logger
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from urllib3.exceptions import MaxRetryError
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import SessionNotCreatedException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from linkedin import models as lin_models
from reusable.models import get_network_model
from reusable.other import only_one_concurrency
from reusable.browser import scroll
from notification import tasks as not_tasks
from notification.utils import telegram_text_purify

logger = get_task_logger(__name__)
MINUTE = 60
TASKS_TIMEOUT = 1 * MINUTE
DUPLICATE_CHECKER = redis.StrictRedis(host="social_redis", port=6379, db=5)


def get_config():
    config_model = get_network_model("Config")
    config = config_model.objects.last()
    if config is None:
        config = config_model(crawl_linkedin_feed=False)
    return config


def get_driver():
    """This function creates a browser driver and returns it

    Returns:
        Webdriver: webdriver browser
    """
    try:
        return webdriver.Remote(
            "http://social_firefox:4444/wd/hub",
            DesiredCapabilities.FIREFOX,
            options=webdriver.FirefoxOptions(),
        )
    except SessionNotCreatedException as error:
        logger.info("Error: %s\n\n%s", error, traceback.format_exc())
    except MaxRetryError as error:
        logger.info("Error: %s\n\n%s", error, traceback.format_exc())
    # Should do appropriate action instead of exit (for example restarting docker)
    sys.exit()


def initialize_linkedin_driver():
    """This function head the browser to the LinkedIn website.

    Returns:
        Webdriver: webdriver browser
    """
    driver = get_driver()

    cookies = None
    with open("/app/social/linkedin_cookies.pkl", "rb") as linkedin_cookie:
        cookies = pickle.load(linkedin_cookie)

    driver.get("https://www.linkedin.com/")
    for cookie in cookies:
        driver.add_cookie(cookie)
    return driver


def driver_exit(driver):
    """This function properly exit a web driver.
    It ensures that we wait for some seconds before exiting the browser.

    Args:
        driver (Webdriver): webdriver browser
    """
    time.sleep(2)
    driver.quit()


@shared_task
def login():
    """This function login into LinkedIn and store credential info into /app/social/cookies.pkl .
    It read username and password from environment variables as follow:
    LINKEDIN_EMAIL -> username
    LINKEDIN_PASSWORD -> password
    """
    driver = get_driver()
    driver.get("https://www.linkedin.com/login")
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        email_elem = driver.find_element("id", "username")
        email_elem.send_keys(settings.LINKEDIN_EMAIL)
        password_elem = driver.find_element("id", "password")
        password_elem.send_keys(settings.LINKEDIN_PASSWORD)
        password_elem.submit()
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "global-nav-search"))
        )

        with open("/app/social/linkedin_cookies.pkl", "wb") as linkedin_cookie:
            pickle.dump(driver.get_cookies(), linkedin_cookie)

    except NoSuchElementException:
        logger.error(traceback.format_exc())
    finally:
        driver_exit(driver)


@shared_task
def store_posts(channel_id, post_id, body, meta_data):
    """This function store a post into database. It will create or update a post.
    If a post with post-id exists, It will update it. Otherwise it will create a new post.

    Args:
        channel_id (int): id of channel
        post_id (int): id of post
        body (str): body of the post
        reaction_count (int): reactions count
        comment_count (int): comments count
        share_count (int): shares count
    """
    post_model = get_network_model("Post")
    exists = post_model.objects.filter(
        network_id=post_id, channel_id=channel_id
    ).exists()
    share_count = meta_data.get("share_count", 0)
    comment_count = meta_data.get("comment_count", 0)
    reaction_count = meta_data.get("reaction_count", 0)
    if not exists:
        post_model.objects.create(
            channel_id=channel_id,
            network_id=post_id,
            body=body,
            data=meta_data,
            share_count=share_count,
            views_count=reaction_count + comment_count + share_count,
        )
    else:
        post = post_model.objects.get(network_id=post_id)
        post.share_count = share_count
        post.views_count = reaction_count + comment_count + share_count
        post.data = meta_data
        post.save()


def get_post_statistics(reaction_element):
    statistics = {
        "reaction_count": 0,
        "comment_count": 0,
        "share_counter": 0,
    }
    socials = reaction_element.find_elements(By.XPATH, ".//li")
    for social in socials:
        temp = social.get_attribute("aria-label")
        if not temp:
            temp = social.find_elements(By.XPATH, ".//button")
            temp = temp[0].get_attribute("aria-label")
        temp = temp.split()[:2]
        value, elem = int(temp[0].replace(",", "")), temp[1]
        if elem == "reactions":
            statistics["reaction_count"] = value
        elif elem == "comments":
            statistics["comment_count"] = value
        elif elem == "shares":
            statistics["share_count"] = value
    return statistics


@shared_task(name="get_linkedin_posts")
@only_one_concurrency(key="browser1", timeout=TASKS_TIMEOUT)
def get_linkedin_posts(channel_id):
    channel_model = get_network_model("Channel")
    channel = channel_model.objects.get(pk=channel_id)
    channel_url = channel.username
    driver = initialize_linkedin_driver()
    driver.get(channel_url)
    scroll(driver, 1)
    time.sleep(5)
    try:
        articles = driver.find_elements(By.CLASS_NAME, "feed-shared-update-v2")
        for article in articles:
            try:
                post_id = article.get_attribute("data-urn")
                body = article.find_element(By.CLASS_NAME, "break-words").text
                reaction = article.find_elements(
                    By.XPATH,
                    './/ul[contains(@class, "social-details-social-counts")]',
                )[0]
                statistics = get_post_statistics(reaction)
                store_posts.delay(channel_id, post_id, body, statistics)
            except NoSuchElementException:
                logger.error(traceback.format_exc())
    except NoSuchElementException:
        logger.error(traceback.format_exc())
    finally:
        driver_exit(driver)
        channel.last_crawl = timezone.localtime()
        channel.save()


def sort_by_recent(driver):
    sort = driver.find_element(
        "xpath",
        "//button[@class='display-flex full-width \
            artdeco-dropdown__trigger artdeco-dropdown__trigger--placement-bottom ember-view']",
    )
    if "recent" not in sort.text:
        sort.click()
        time.sleep(5)
        sort_button = driver.find_element(
            "xpath",
            "//button[@class='display-flex \
                full-width artdeco-dropdown__trigger artdeco-dropdown__trigger--placement-bottom \
                    ember-view']/following-sibling::div",
        )
        sort_button = sort_button.find_elements("tag name", "li")[1]
        sort_button.click()
        time.sleep(5)
    return driver


@shared_task
def get_linkedin_feed():
    config_model = get_network_model("Config")
    config = config_model.objects.last()
    if config is None or not config.crawl_linkedin_feed:
        return
    driver = initialize_linkedin_driver()
    driver.get("https://www.linkedin.com/feed/")
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.ID, "global-nav-search"))
    )
    driver = sort_by_recent(driver)
    scroll(driver, 5)
    time.sleep(5)
    articles = driver.find_elements(
        By.XPATH,
        './/div[starts-with(@data-id, "urn:li:activity:")]',
    )
    for article in articles:
        try:
            driver.execute_script("arguments[0].scrollIntoView();", article)
            time.sleep(2)
            feed_id = article.get_attribute("data-id")
            body = article.find_element(
                By.CLASS_NAME, "feed-shared-update-v2__commentary"
            ).text
            if DUPLICATE_CHECKER.exists(feed_id):
                continue
            DUPLICATE_CHECKER.set(feed_id, "", ex=86400 * 30)
            link = f"https://www.linkedin.com/feed/update/{feed_id}/"
            body = telegram_text_purify(body)
            message = f"{body}\n\n{link}"
            not_tasks.send_telegram_message(strip_tags(message))
            time.sleep(3)
        except NoSuchElementException:
            logger.error(traceback.format_exc())
    driver_exit(driver)


@shared_task
def check_job_pages():
    pages = lin_models.JobSearch.objects.filter(enable=True).order_by("-priority")
    for page in pages:
        now = timezone.localtime()
        print(f"{now} start crawling linkedin page {page.name}")
        get_job_page_posts(page.pk)


def remove_redis_keys():
    redis_keys = DUPLICATE_CHECKER.keys("*")
    counter = DUPLICATE_CHECKER.delete(*redis_keys)
    return counter


def sort_by_most_recent(driver):
    filter_button = driver.find_elements(
        By.XPATH,
        './/button[contains(@class, "search-reusables__filter-pill-button")]',
    )
    filter_button[len(filter_button) - 1].click()
    time.sleep(2)
    most_recent_input = driver.find_elements(
        By.XPATH,
        './/label[contains(@for, "advanced-filter-sortBy-DD")]',
    )
    most_recent_input[0].click()
    time.sleep(2)
    apply_button = driver.find_elements(
        By.XPATH,
        './/button[contains(@data-test-reusables-filters-modal-show-results-button, "true")]',
    )
    apply_button[0].click()
    time.sleep(2)
    return driver


def is_english(language):
    """Checks if language term is English or not

    Args:
        language (str): language term

    Returns:
        bool: True if is "en" otherwise is False
    """
    if language != "en":
        return False
    return True


def check_eligible(keyword, job_detail):
    if keyword.lower() in job_detail.lower():
        return False
    return True


def is_eligible(ig_filters, job_detail):
    """Checks if job is eligible or not based on job_detail and ignoring filters
    Details are job's title, job's company, job's location

    Args:
        job_detail (dict): details of job like location, language
        ig_filters (IgnoringFilter): defined filters for a JobSearch

    Returns:
        bool: True if is eligible otherwise is False
    """
    if not is_english(job_detail["language"]):
        return False
    for ig_filter in ig_filters:
        detail = ""
        if ig_filter.place == lin_models.IgnoringFilter.TITLE:
            detail = job_detail["title"]
        elif ig_filter.place == lin_models.IgnoringFilter.COMPANY:
            detail = job_detail["company"]
        elif ig_filter.place == lin_models.IgnoringFilter.LOCATION:
            detail = job_detail["location"]
        if not check_eligible(ig_filter.keyword, detail):
            return False
    return True


def get_job_url(element):
    """Extract selected job url from driver

    Args:
        driver (WebDriver): browser driver

    Returns:
        str: job url
    """
    url = ""
    try:
        url = element.find_element(
            By.CLASS_NAME, "job-card-container__link"
        ).get_attribute("href")
    except NoSuchElementException:
        url = "Cannot-extract-url"
    url = url.split("?")[0]  # remove query params
    return url


def get_job_title(element):
    """Extract selected job title from driver

    Args:
        driver (WebDriver): browser driver

    Returns:
        str: job title
    """
    try:
        return element.find_element(By.CLASS_NAME, "artdeco-entity-lockup__title").text
    except NoSuchElementException:
        return "Cannot-extract-title"


def check_easy_apply(element):
    """Check if job has easy apply option

    Args:
        driver (WebDriver): browser driver

    Returns:
        str: check-mark emoji
    """
    try:
        element.find_element(By.CLASS_NAME, "job-card-container__apply-method")
        return "✅"
    except NoSuchElementException:
        return "❌"


def get_job_location(element):
    """Extract selected job location from driver

    Args:
        driver (WebDriver): browser driver

    Returns:
        str: job location
    """
    try:
        location = element.find_element(
            By.CLASS_NAME, "artdeco-entity-lockup__caption"
        ).text
    except NoSuchElementException:
        return "Cannot-extract-location"
    return location.replace("\n", " | ")


def get_job_company(element):
    """Extract selected job company from driver

    Args:
        driver (WebDriver): browser driver

    Returns:
        str: job company
    """
    try:
        return element.find_element(
            By.CLASS_NAME, "artdeco-entity-lockup__subtitle"
        ).text
    except NoSuchElementException:
        return "Cannot-extract-company"


def get_job_description(driver):
    """Extract selected job description from driver

    Args:
        driver (WebDriver): browser driver

    Returns:
        str: job description
    """
    try:
        return driver.find_element(By.ID, "job-details").text
    except NoSuchElementException:
        return "Cannot-extract-description"


def get_job_company_size(driver):
    """Extract selected job's company size

    Args:
        driver (WebDriver): browser driver

    Returns:
        str: job's company size
    """
    try:
        company_size = driver.find_elements(
            By.CLASS_NAME, "jobs-unified-top-card__job-insight"
        )[1].text
        return company_size.split("·")[0].replace("employees", "")
    except NoSuchElementException:
        return "Cannot-extract-company-size (no such element)"
    except IndexError:
        return "Cannot-extract-company-size (index error)"


def get_language(description):
    try:
        return detect(description)
    except LangDetectException:
        return "Cannot-detect-language"


def check_keywords(body, keywords):
    result = ""
    body = body.lower()
    for keyword in keywords:
        if keyword.lower() in body:
            result += f"\n{keyword}: ✅"
    return result


def send_notification(message, data, keywords, output_channel_pk):
    """This function gets a message template and places the retrieved data into that.
    Then sends it to specified output channel

    Args:
        message (str): message template
        data (dict): dictionary that includes retrieved data
        output_channel_pk (int): primary key of output channel
    """
    not_tasks.send_message_to_telegram_channel(
        message.replace("url", strip_tags(data["url"]))
        .replace("lang", data["language"].upper())
        .replace("title", data["title"])
        .replace("location", data["location"])
        .replace("company", data["company"])
        .replace("size", data["company_size"])
        .replace("easy_apply", data["easy_apply"])
        .replace("keywords", check_keywords(data["description"], keywords)),
        output_channel_pk,
    )


def get_job_detail(driver, element):
    """This function gets browser driver and job html content and returns some
    information like job-link, job-desc and job-language.

    Args:
        driver (Webdriver): browser webdriver
        element (HTMLElement): html element of job

    Returns:
        result (dict): consist of information about job: link, description, language, title,
            location, company
    """
    result = {}
    result["url"] = get_job_url(element)
    result["easy_apply"] = check_easy_apply(element)
    result["description"] = get_job_description(driver)
    result["company_size"] = get_job_company_size(driver)
    result["language"] = get_language(result["description"])
    result["title"] = telegram_text_purify(get_job_title(element))
    result["location"] = telegram_text_purify(get_job_location(element))
    result["company"] = telegram_text_purify(get_job_company(element))
    return result


def get_card_id(element):
    try:
        return element.find_element(
            By.XPATH,
            './/div[starts-with(@data-urn, "urn:li:activity:")]',
        ).get_attribute("data-urn")
    except NoSuchElementException:
        return "Cannot-extract-card-id"


@shared_task
def check_page_count(page_id, ignore_repetitive, starting_job):
    page = lin_models.JobSearch.objects.get(pk=page_id)
    if page.page_count == 1:
        return
    if starting_job != ((page.page_count - 1) * 25):
        get_job_page_posts.delay(page_id, ignore_repetitive, starting_job + 25)


@shared_task
def update_job_search_last_crawl_at(page_id):
    lin_models.JobSearch.objects.filter(pk=page_id).update(
        last_crawl_at=timezone.localtime()
    )


@shared_task
def get_job_page_posts(page_id, ignore_repetitive=True, starting_job=0):
    page = lin_models.JobSearch.objects.get(pk=page_id)
    message, url, output_channel, keywords, ig_filters = page.page_data
    driver = initialize_linkedin_driver()
    url = f"{url}&start={starting_job}"
    driver.get(url)
    time.sleep(5)
    driver = sort_by_most_recent(driver)  # It seems that we don't need this anymore
    items = driver.find_elements(By.CLASS_NAME, "jobs-search-results__list-item")
    counter = 0
    for item in items:
        try:
            driver.execute_script("arguments[0].scrollIntoView();", item)
            job_id = item.get_attribute("data-occludable-job-id")
            # if id is none or is repetitive
            if not job_id or (ignore_repetitive and DUPLICATE_CHECKER.exists(job_id)):
                continue
            DUPLICATE_CHECKER.set(job_id, "", ex=86400 * 30)
            item.click()
            time.sleep(2)
            job_detail = get_job_detail(driver, item)
            if not is_eligible(ig_filters, job_detail):
                store_ignored_content.delay(job_detail)
                continue
            send_notification(message, job_detail, keywords, output_channel)
            counter += 1
        except StaleElementReferenceException:
            logger.warning("stale element exception")
            break
        except NoSuchElementException:
            logger.error(traceback.format_exc())
    print(f"found {counter} job in page: {page_id} with starting-job: {starting_job}")
    check_page_count.delay(page_id, ignore_repetitive, starting_job)
    update_job_search_last_crawl_at.delay(page_id)
    driver_exit(driver)


@shared_task
def update_expression_search_last_crawl_at(page_id):
    lin_models.ExpressionSearch.objects.filter(pk=page_id).update(
        last_crawl_at=timezone.localtime()
    )


@shared_task
def get_expression_search_posts(page_id, ignore_repetitive=True):
    page = lin_models.ExpressionSearch.objects.get(pk=page_id)
    driver = initialize_linkedin_driver()
    driver.get(page.url)
    time.sleep(5)
    articles = driver.find_elements(By.CLASS_NAME, "artdeco-card")
    counter = 0
    for article in articles:
        try:
            driver.execute_script("arguments[0].scrollIntoView();", article)
            time.sleep(2)
            post_id = get_card_id(article)
            if not post_id or (ignore_repetitive and DUPLICATE_CHECKER.exists(post_id)):
                print(f"id is none or duplicate, id: {post_id}")
                continue
            DUPLICATE_CHECKER.set(post_id, "", ex=86400 * 30)
            body = ""
            try:
                body = article.find_element(
                    By.CLASS_NAME, "feed-shared-update-v2__commentary"
                ).text
            except NoSuchElementException:
                print("No such element exception")
                body = "Cannot-extract-body"
            link = f"https://www.linkedin.com/feed/update/{post_id}/"
            body = telegram_text_purify(body)
            message = f"{body}\n\n{link}"
            not_tasks.send_message_to_telegram_channel(
                strip_tags(message), page.output_channel.pk
            )
            counter += 1
            time.sleep(3)
        except NoSuchElementException:
            logger.error(traceback.format_exc())
    print(f"found {counter} post in page {page_id}")
    update_expression_search_last_crawl_at.delay(page.pk)
    driver_exit(driver)


@shared_task
def check_expression_search_pages():
    pages = lin_models.ExpressionSearch.objects.filter(enable=True)
    for page in pages:
        start_time = timezone.localtime()
        print(f"{start_time} Start crawling linkedin page {page.name}")
        get_expression_search_posts(page.pk)


@shared_task
def store_ignored_content(job_detail):
    job_detail.pop("company_size", None)  # Remove extra key
    job_detail.pop("easy_apply", None)  # Remove extra key
    lin_models.IgnoredJob.objects.create(**job_detail)
