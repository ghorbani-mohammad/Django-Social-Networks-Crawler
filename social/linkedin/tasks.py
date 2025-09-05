import pickle
import sys
import time
import traceback
from typing import Optional, Tuple

import redis
import requests
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.test import RequestFactory
from django.utils import timezone
from django.utils.html import strip_tags
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from selenium import webdriver
from selenium.common.exceptions import (NoSuchElementException,
                                        SessionNotCreatedException,
                                        StaleElementReferenceException,
                                        TimeoutException)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from urllib3.exceptions import MaxRetryError

from ai.chatgpt.main import get_cover_letter
from linkedin import models as lin_models
from notification import tasks as not_tasks
from notification.utils import (collapse_newlines, html_link, limit_words,
                                normalize_job_message_spacing,
                                strip_accessibility_hashtag_labels,
                                telegram_text_purify)
from reusable.browser import scroll
from reusable.models import get_network_model
from reusable.other import only_one_concurrency

logger = get_task_logger(__name__)
MINUTE = 60
TASKS_TIMEOUT = 1 * MINUTE
DUPLICATE_CHECKER = redis.StrictRedis(host="social_redis", port=6379, db=5)
LINKEDIN_URL = "https://www.linkedin.com/"


def send_websocket_notification(job_instance):
    """Send job notification to all connected WebSocket clients."""
    from .serializers import JobSerializer

    try:
        websocket_url = "http://social_websocket:3000/api/broadcast-job"

        # Create a mock request context for absolute URL generation
        factory = RequestFactory()
        request = factory.get("/")
        # Use Django's ALLOWED_HOSTS or default to localhost
        host = (
            getattr(settings, "ALLOWED_HOSTS", ["localhost"])[0]
            if settings.ALLOWED_HOSTS
            else "localhost"
        )
        request.META["HTTP_HOST"] = f"{host}:8000"

        serializer = JobSerializer(job_instance, context={"request": request})
        payload = {"job": serializer.data}

        response = requests.post(
            websocket_url,
            json=payload,
            timeout=5,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            logger.info(f"WebSocket notification sent for job: {job_data.get('title')}")
        else:
            logger.error(
                f"Failed to send WebSocket notification: {response.status_code}"
            )

    except Exception as e:
        logger.error(f"Error sending WebSocket notification: {str(e)}")


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

    driver.get(LINKEDIN_URL)
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
    driver.get(f"{LINKEDIN_URL}login")
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
        logger.info("Logged in to LinkedIn")

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
    driver.get(f"{LINKEDIN_URL}feed/")
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
            link = f"{LINKEDIN_URL}feed/update/{feed_id}/"
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
        logger.info("%s start crawling linkedin page %s", now, page.name)
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
    return keyword.lower() not in job_detail.lower()


def is_eligible(
    ig_filters, just_easily_apply: bool, job_detail: dict
) -> Tuple[bool, Optional[str]]:
    """Checks if job is eligible or not based on job_detail and ignoring filters
    Details are job's title, job's company, job's location

    Args:
        job_detail (dict): details of job like location, language
        ig_filters (IgnoringFilter): defined filters for a JobSearch

    Returns:
        bool: True if is eligible otherwise is False
    """
    if just_easily_apply and job_detail["easy_apply"] == "❌":
        return False, "easy_apply"
    if not is_english(job_detail["language"]):
        return False, "language"
    for ig_filter in ig_filters:
        detail, reason = "", ""
        if ig_filter.place == lin_models.IgnoringFilter.TITLE:
            detail, reason = job_detail["title"], "title"
        elif ig_filter.place == lin_models.IgnoringFilter.COMPANY:
            detail, reason = job_detail["company"], "company"
        elif ig_filter.place == lin_models.IgnoringFilter.LOCATION:
            detail, reason = job_detail["location"], "location"
        if not check_eligible(ig_filter.keyword, detail):
            return False, reason
    return True, None


def get_job_url(element: WebElement):
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


def get_job_title(element: WebElement):
    """Extract selected job title from driver

    Args:
        driver (WebDriver): browser driver

    Returns:
        str: job title
    """
    try:
        title_element = element.find_element(
            By.CLASS_NAME, "artdeco-entity-lockup__title"
        )
        if title_element.find_element(By.TAG_NAME, "strong"):
            return title_element.find_element(By.TAG_NAME, "strong").text
        return title_element.text
    except NoSuchElementException:
        return "Cannot-extract-title"


def check_easy_apply(element: WebElement):
    """Check if job has easy apply option

    Args:
        driver (element): job element

    Returns:
        str: check-mark emoji
    """
    try:
        # if found then it has easy apply option
        element.find_element(
            By.XPATH,
            './/*[local-name()="svg" and @data-test-icon="linkedin-bug-color-small"]',
        )
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
        company_size_el = driver.find_elements(
            By.CLASS_NAME, "job-details-jobs-unified-top-card__job-insight"
        )
        if not company_size_el:
            return "N/A"
        company_size = company_size_el[1].text
        return company_size.split("·")[0].replace("employees", "")
    except NoSuchElementException:
        return "N/A"
    except IndexError:
        return "N/A"


def get_language(description):
    try:
        return detect(description)
    except LangDetectException:
        return "Cannot-detect-language"


def check_keywords(body, keywords):
    body_lower = body.lower() if isinstance(body, str) else ""
    hits = []
    for keyword in keywords:
        if not keyword:
            continue
        if keyword.lower() in body_lower:
            hits.append(f"#{keyword}")
    if not hits:
        return ""
    # Ensure one blank line before the hashtag block
    return "\n\n" + "\n".join(hits)


@shared_task
def send_notification(message, data, keywords, output_channel_pk, cover_letter: str):
    """This function gets a message template and places the retrieved data into that.
    Then sends it to specified output channel

    Args:
        message (str): message template
        data (dict): dictionary that includes retrieved data
        output_channel_pk (int): primary key of output channel
    """
    message = (
        message.replace("lang", data["language"].upper())
        .replace("title", data["title"])
        .replace("location", data["location"])
        .replace("company", data["company"])
        .replace("size", data["company_size"])
        .replace("easy_apply", data["easy_apply"])
        .replace("id", str(data["id"]))
        .replace("keywords", check_keywords(data["description"], keywords))
    )
    # Ensure exactly one blank line before URL
    url_text = strip_tags(data["url"]) if data.get("url") else ""
    message = message.replace("url", f"\n\n{url_text}")
    # Only append cover letter spacing if there is a cover letter
    if cover_letter:
        message = f"{message}\n\n{cover_letter}"
    # Enforce desired spacing around Region, Location and Easy Apply blocks
    message = normalize_job_message_spacing(message)
    # Ensure there is exactly one blank line before the url if present in template
    # Otherwise, append link will already be defined in the template
    message = collapse_newlines(message, 1)
    not_tasks.send_message_to_telegram_channel(
        message,
        output_channel_pk,
        True,
    )


@shared_task
def store_job(job_detail: dict, page_id: int, eligible: bool, reason: Optional[str]):
    """Create or update a Job row for every crawled job."""
    try:
        job_values = {
            "url": job_detail.get("url"),
            "title": job_detail.get("title"),
            "company": job_detail.get("company"),
            "location": job_detail.get("location"),
            "description": job_detail.get("description"),
            "language": job_detail.get("language"),
            "company_size": job_detail.get("company_size"),
            "easy_apply": True if job_detail.get("easy_apply") == "✅" else False,
            "eligible": eligible,
            "rejected_reason": reason,
        }
        # include page relation
        job_values["page_id"] = page_id

        network_id = job_detail.get("network_id")
        if network_id:
            obj, created = lin_models.Job.objects.update_or_create(
                network_id=network_id, defaults=job_values
            )
        else:
            obj = lin_models.Job.objects.create(**job_values)
            created = True
        # compute and attach matched keywords based on JobSearch.page keywords
        try:
            page = lin_models.JobSearch.objects.get(pk=page_id)
            # Flatten page keywords (words CSV) into tokens
            matched = []
            haystack = " ".join(
                [
                    (job_values.get("title") or ""),
                    (job_values.get("company") or ""),
                    (job_values.get("location") or ""),
                    (job_values.get("description") or ""),
                ]
            )
            body_lower = haystack.lower()
            for keyword in page.keywords.all():
                hit = False
                for token in keyword.keywords_in_array:
                    if token and token.lower() in body_lower:
                        hit = True
                        break
                if hit:
                    matched.append(keyword)
            if matched:
                obj.matched_keywords.set(matched)
            else:
                obj.matched_keywords.clear()
        except Exception:
            logger.error("Failed to compute matched keywords", exc_info=True)

        # Schedule async task to search for keywords in description after 10 seconds
        from celery import current_app

        current_app.send_task(
            "linkedin.tasks.search_keywords_in_job_description",
            args=[obj.pk],
            countdown=10,
        )

        # WebSocket notification is now handled by the post_save signal

        return obj.pk
    except Exception:
        logger.error("Failed to store Job", exc_info=True)
        return None


def get_job_detail(driver, element) -> dict:
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
    result["network_id"] = element.get_attribute("data-occludable-job-id")
    result["easy_apply"] = check_easy_apply(element)
    result["description"] = get_job_description(driver)
    result["company_size"] = get_job_company_size(driver)
    result["language"] = get_language(result["description"])
    result["title"] = telegram_text_purify(get_job_title(element))
    result["location"] = telegram_text_purify(get_job_location(element))
    result["company"] = telegram_text_purify(get_job_company(element))
    return result


def get_card_id(element) -> str:
    """Tries to extract card id from element.

    Args:
        element (HTMLElement): job card element

    Returns:
        str: id of card
    """
    # Try on the element itself first
    try:
        self_urn = element.get_attribute("data-urn")
        if self_urn and self_urn.startswith("urn:li:activity:"):
            return self_urn
    except Exception:
        pass
    try:
        self_id = element.get_attribute("data-id")
        if self_id and self_id.startswith("urn:li:activity:"):
            return self_id
    except Exception:
        pass

    # Then try descendants: data-urn first, then data-id
    try:
        return element.find_element(
            By.XPATH,
            './/div[starts-with(@data-urn, "urn:li:activity:")]',
        ).get_attribute("data-urn")
    except NoSuchElementException:
        try:
            return element.find_element(
                By.XPATH,
                './/div[starts-with(@data-id, "urn:li:activity:")]',
            ).get_attribute("data-id")
        except NoSuchElementException:
            return "Cannot-extract-card-id"


@shared_task
def check_page_count(page_id: int, ignore_repetitive: bool, starting_job: int):
    """Check if we should crawl next page or not.

    Args:
        page_id (int): the primary key of JobSearch obj.
        ignore_repetitive (bool): ignore repetitive jobs or not.
        starting_job (int): the starting job of current page.
    """
    page = lin_models.JobSearch.objects.get(pk=page_id)
    if page.page_count == 1:
        return
    if starting_job != ((page.page_count - 1) * 25):
        get_job_page_posts.delay(page_id, ignore_repetitive, starting_job + 25)


@shared_task
def update_job_search_last_crawl_at(page_id: int, counter: int):
    """Update last_crawl_at field of JobSearch object.
        Will be updated after crawling each page.
        To current time.

    Args:
        page_id (int): the primary key of JobSearch obj.
        counter (int): number of jobs found in this crawl
    """
    # Simply update with the most recent crawl count
    lin_models.JobSearch.objects.filter(pk=page_id).update(
        last_crawl_at=timezone.localtime(), last_crawl_count=counter
    )


@shared_task
def get_job_page_posts(
    page_id: int, ignore_repetitive: bool = True, starting_job: int = 0
):
    """
    This function gets a page id and crawl its jobs.
    """
    page = lin_models.JobSearch.objects.get(pk=page_id)
    (
        message,
        url,
        output_channel,
        keywords,
        ig_filters,
        just_easily_apply,
    ) = page.page_data
    try:
        # Remove the 'with' statement - it's not a context manager
        driver = initialize_linkedin_driver()
        prepare_driver(driver, url, starting_job)
        time.sleep(5)
        items = driver.find_elements(By.CLASS_NAME, "scaffold-layout__list-item")
        counter = process_items(
            driver,
            items,
            ignore_repetitive,
            message,
            keywords,
            output_channel,
            ig_filters,
            just_easily_apply,
            page.profile.about_me,
            page.pk,
        )
    finally:
        # Always ensure driver is properly closed
        if "driver" in locals():
            driver_exit(driver)
    logger.info(
        f"found {counter} jobs in page: {page_id} with starting-job: {starting_job}"
    )
    update_job_search_last_crawl_at.delay(page_id, counter)
    check_page_count.delay(page_id, ignore_repetitive, starting_job)


def prepare_driver(driver, url, starting_job):
    full_url = f"{url}&start={starting_job}"
    driver.get(full_url)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )  # Wait for page load


def process_items(
    driver,
    items,
    ignore_repetitive,
    message,
    keywords,
    output_channel,
    ig_filters,
    just_easily_apply: bool,
    about_profile: str,
    page_id: int,
):
    counter = 0
    for item in items:
        try:
            job_id = process_job_item(
                driver,
                item,
                ignore_repetitive,
                message,
                keywords,
                output_channel,
                ig_filters,
                just_easily_apply,
                about_profile,
                page_id,
            )
            if job_id:
                counter += 1
        except StaleElementReferenceException:
            logger.warning("Stale element reference exception")
            break
        except NoSuchElementException:
            logger.error("No such element exception", exc_info=True)
        except Exception:
            logger.error("Unhandled exception in process_items", exc_info=True)
    return counter


def process_job_item(
    driver,
    item,
    ignore_repetitive,
    message,
    keywords,
    output_channel,
    ig_filters,
    just_easily_apply: bool,
    about_profile: str,
    page_id: int,
):
    driver.execute_script("arguments[0].scrollIntoView();", item)
    job_id = item.get_attribute("data-occludable-job-id")
    logger.info(f"Processing job_id: {job_id}")

    if not job_id or (ignore_repetitive and DUPLICATE_CHECKER.exists(job_id)):
        return None
    DUPLICATE_CHECKER.set(job_id, "", ex=86400 * 30)

    item.click()
    time.sleep(2)
    # WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "job-detail")))
    job_detail = get_job_detail(driver, item)

    # Check if company is in ignored accounts for this job search
    company = job_detail.get("company", "")
    if company and company != "Cannot-extract-company":
        page = lin_models.JobSearch.objects.get(pk=page_id)
        if is_poster_in_ignored_accounts(company, page=page):
            logger.info(f"Skipping job {job_id} due to ignored company: {company}")
            # Store as ignored content with reason
            store_ignored_content.delay(job_detail, "ignored_company")
            return None

    # cover_letter = get_cover_letter(about_profile, job_detail["description"])
    # logger.info(f"cover_letter: {cover_letter}")
    cover_letter = ""

    eligible, reason = is_eligible(ig_filters, just_easily_apply, job_detail)
    # Persist every crawled job with decision
    # The post_save signal will handle sending notifications for eligible jobs
    store_job.delay(job_detail, page_id, eligible, reason)
    if not eligible:
        logger.info(f"Job is not eligible, reason: {reason}")
        store_ignored_content.delay(job_detail, reason)
        return None

    time.sleep(2)  # Delay between sending each message
    return job_id


@shared_task
def update_expression_search_last_crawl_at(page_id):
    lin_models.ExpressionSearch.objects.filter(pk=page_id).update(
        last_crawl_at=timezone.localtime()
    )


@shared_task
def get_expression_search_posts(expr_id, ignore_repetitive=True):
    try:
        expr = lin_models.ExpressionSearch.objects.get(pk=expr_id)
        with initialize_linkedin_driver() as driver:
            driver.get(expr.url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Load more results by scrolling before collecting cards
            scroll(driver, 8)
            time.sleep(3)

            try:
                articles = driver.find_elements(By.CLASS_NAME, "artdeco-card")
            except StaleElementReferenceException:
                logger.warning("Stale element reference exception")
                return

            logger.info("Detected %s potential cards", len(articles))

            counter = process_articles(driver, articles, ignore_repetitive, expr)

        logger.info("found %s post in page %s", counter, expr_id)
        update_expression_search_last_crawl_at.delay(expr.pk)
    except Exception as e:
        logger.error(f"Error in get_expression_search_posts: {e}")


def process_articles(driver, articles, ignore_repetitive, expr):
    counter = 0
    for article in articles:
        try:
            sent = process_article(driver, article, ignore_repetitive, expr)
            if sent:
                counter += 1
        except NoSuchElementException:
            logger.error("Element not found", exc_info=True)
        except TimeoutException:
            logger.error("Timeout waiting for element", exc_info=True)
    return counter


def get_poster(article) -> Optional[str]:
    """Extract the poster name from the article, avoiding duplication."""
    try:
        # Find the actor element
        actor_element = article.find_element(
            By.CLASS_NAME, "update-components-actor__single-line-truncate"
        )

        # Try to get text from aria-hidden span first (usually the main text)
        try:
            aria_hidden_span = actor_element.find_element(
                By.XPATH, './/span[@aria-hidden="true"]'
            )
            poster_text = aria_hidden_span.text.strip()
            if poster_text:
                return poster_text
        except NoSuchElementException:
            pass

        # Fallback to the main element text, but clean it up
        poster_text = actor_element.text.strip()
        if poster_text:
            # Remove any duplicate text by taking only the first occurrence
            # Split by common separators and take the first non-empty part
            parts = poster_text.split("\n")
            for part in parts:
                cleaned_part = part.strip()
                if cleaned_part:
                    return cleaned_part

        return None
    except NoSuchElementException:
        return None


def process_article(driver, article, ignore_repetitive, expr):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", article)
    try:
        ActionChains(driver).move_to_element(article).perform()
    except Exception:
        # Ignore move errors; scrollIntoView is usually enough
        pass
    # Give the DOM a moment to lazy-load nested content
    try:
        WebDriverWait(driver, 5).until(
            lambda d: (
                len(
                    article.find_elements(
                        By.XPATH, './/div[starts-with(@data-urn, "urn:li:activity:")]'
                    )
                )
                > 0
                or len(
                    article.find_elements(
                        By.XPATH, './/div[starts-with(@data-id, "urn:li:activity:")]'
                    )
                )
                > 0
            )
        )
    except TimeoutException:
        pass
    post_id = get_card_id(article)
    poster = get_poster(article)
    if poster:
        # Check if poster is in ignored accounts for this expression search
        if is_poster_in_ignored_accounts(poster, expr=expr):
            logger.info(f"Skipping post {post_id} due to ignored poster: {poster}")
            return False

    if post_id == "Cannot-extract-card-id":
        logger.info("Cannot extract card id")
        return False
    if not post_id or (ignore_repetitive and DUPLICATE_CHECKER.exists(post_id)):
        logger.info(f"id is none or duplicate, id: {post_id}")
        return False
    DUPLICATE_CHECKER.set(post_id, "", ex=86400 * 30)
    body = extract_body(article)
    body = strip_accessibility_hashtag_labels(body)
    body = collapse_newlines(body, 1)
    # Skip posts containing ignored keywords related to the expression's ignored categories
    try:
        ignore_categories = expr.ignore_categories.filter(enable=True)
        if ignore_categories.exists():
            ignored_keywords = lin_models.IgnoringFilter.objects.filter(
                enable=True, category__in=ignore_categories
            ).values_list("keyword", flat=True)
            body_lower = body.lower()
            for ignored_keyword in ignored_keywords:
                if ignored_keyword in body_lower:
                    logger.info(
                        f"Skipping post {post_id} due to ignored keyword: {ignored_keyword}"
                    )
                    return False
    except Exception:
        logger.error("Error checking ignored keywords", exc_info=True)
    # Ignore articles that are not in English or Persian
    language = get_language(body)
    if language not in ("en", "fa"):
        logger.info(
            f"Skipping post {post_id} due to non-supported language: {language}"
        )
        return False
    body = limit_words(body, 50)
    # Add poster to body if available
    if poster:
        body = f"{expr.name}\n\nPosted by: {poster}\n\n{body}"
    else:
        body = f"{expr.name}\n\n{body}"
    link = f"https://www.linkedin.com/feed/update/{post_id}/"
    message = f"{body}\n\n{html_link(link, link)}"
    time.sleep(2)  # Delay between sending each message
    not_tasks.send_message_to_telegram_channel(
        message, expr.output_channel.pk, html=True
    )
    return True


def extract_body(article):
    try:
        return article.find_element(
            By.CLASS_NAME, "feed-shared-update-v2__description"
        ).text
    except NoSuchElementException:
        try:
            return article.find_element(
                By.CLASS_NAME, "feed-shared-update-v2__commentary"
            ).text
        except NoSuchElementException:
            try:
                return article.find_element(
                    By.XPATH,
                    './/*[contains(@class, "update-components-text") or contains(@class, "break-words")]',
                ).text
            except NoSuchElementException:
                logger.info("No such element exception")
                return "Cannot-extract-body"


@shared_task
def check_expression_search_pages():
    pages = lin_models.ExpressionSearch.objects.filter(enable=True)
    for page in pages:
        start_time = timezone.localtime()
        logger.info(f"{start_time} Start crawling linkedin page {page.name}")
        get_expression_search_posts(page.pk)


@shared_task
def store_ignored_content(job_detail, reason: str):
    # Remove keys not present on IgnoredJob model
    job_detail.pop("company_size", None)
    job_detail.pop("easy_apply", None)
    job_detail.pop("network_id", None)

    # Truncate fields to model max lengths (only if they are strings)
    if isinstance(job_detail.get("title"), str):
        job_detail["title"] = job_detail["title"][:300]
    if isinstance(job_detail.get("location"), str):
        job_detail["location"] = job_detail["location"][:200]
    if isinstance(job_detail.get("company"), str):
        job_detail["company"] = job_detail["company"][:100]
    if isinstance(job_detail.get("language"), str):
        job_detail["language"] = job_detail["language"][:40]

    job_detail["reason"] = reason
    lin_models.IgnoredJob.objects.create(**job_detail)


@shared_task
def find_tags_in_ignored_jobs(limit: int = 0):
    """Scan IgnoredJob title/description for Tag names and report matches.

    Args:
        limit (int): If > 0, only scan the most recent N IgnoredJob rows.

    Returns:
        list[dict]: Each item like {"ignored_job_id": int, "tags": list[str]}.
    """

    limit = 50

    tag_model = get_network_model("Tag")
    tag_names = list(tag_model.objects.values_list("name", flat=True))
    if not tag_names:
        logger.info("No tags defined; skipping find_tags_in_ignored_jobs")
        return []

    # Pre-compute lower-cased names for substring checks
    tag_name_pairs = [(name, name.lower()) for name in tag_names if name]

    queryset = lin_models.IgnoredJob.objects.order_by("-created_at")
    if limit and limit > 0:
        queryset = queryset[:limit]

    results = []
    for ignored_job in queryset.iterator():
        haystack = f"{ignored_job.title or ''} {ignored_job.description or ''}".lower()
        if not haystack.strip():
            continue
        matched = [orig for (orig, low) in tag_name_pairs if low in haystack]
        if matched:
            logger.info(
                "IgnoredJob(%s) matched tags: %s | url=%s",
                ignored_job.pk,
                ", ".join(matched),
                ignored_job.url,
            )
            results.append({"ignored_job_id": ignored_job.pk, "tags": matched})

    logger.info(
        "find_tags_in_ignored_jobs completed; %s jobs with matches", len(results)
    )
    return results


@shared_task
def search_keywords_in_job_description(job_id: int):
    """Search for keywords in job description and update found_keywords field.

    This task runs asynchronously after job creation to find which keywords
    are actually present in the job description.

    Args:
        job_id (int): ID of the job to process
    """
    try:
        job = lin_models.Job.objects.get(pk=job_id)
        if not job.description:
            logger.info(f"Job {job_id} has no description, skipping keyword search")
            return

        # Get all keywords from the job's page
        if not job.page:
            logger.info(f"Job {job_id} has no associated page, skipping keyword search")
            return

        page_keywords = job.page.keywords.all()
        if not page_keywords.exists():
            logger.info(f"Job {job_id} page has no keywords, skipping keyword search")
            return

        # Search for keywords in description
        description_lower = job.description.lower()
        found_keywords = []

        for keyword in page_keywords:
            for token in keyword.keywords_in_array:
                if token and token.lower() in description_lower:
                    found_keywords.append(token)
                    break  # Found one token from this keyword, move to next keyword

        # Update the found_keywords field
        if found_keywords:
            job.found_keywords = ", ".join(found_keywords)
            logger.info(f"Job {job_id} found keywords: {', '.join(found_keywords)}")
        else:
            job.found_keywords = ""
            logger.info(f"Job {job_id} found no keywords in description")

        job.save(update_fields=["found_keywords"])

    except lin_models.Job.DoesNotExist:
        logger.error(f"Job {job_id} not found for keyword search")
    except Exception as e:
        logger.error(
            f"Error searching keywords for job {job_id}: {str(e)}", exc_info=True
        )


def is_poster_in_ignored_accounts(poster: str, expr=None, page=None) -> bool:
    """
    Check if the poster is in any IgnoredAccount for the given job search or expression search.

    Args:
        poster (str): The poster name to check
        expr (ExpressionSearch, optional): The expression search object
        page (JobSearch, optional): The job search object

    Returns:
        bool: True if poster is in ignored accounts, False otherwise
    """
    if not poster:
        return False

    # Get all IgnoredAccount objects that are related to this search
    ignored_accounts = lin_models.IgnoredAccount.objects.none()

    if expr:
        # For expression search, get accounts related to this expression
        ignored_accounts = lin_models.IgnoredAccount.objects.filter(
            expression_search=expr
        )
    elif page:
        # For job search, get accounts related to this job search
        ignored_accounts = lin_models.IgnoredAccount.objects.filter(job_search=page)

    if not ignored_accounts.exists():
        return False

    # Check if any of the ignored account names contain the poster
    poster_lower = poster.lower()
    for ignored_account in ignored_accounts:
        if (
            ignored_account.account_name
            and ignored_account.account_name.lower() in poster_lower
        ):
            logger.info(
                f"Poster '{poster}' matches ignored account: {ignored_account.account_name}"
            )
            return True
        # Also check if poster contains the ignored account name (for partial matches)
        if (
            ignored_account.account_name
            and poster_lower in ignored_account.account_name.lower()
        ):
            logger.info(
                f"Poster '{poster}' matches ignored account: {ignored_account.account_name}"
            )
            return True

    return False
