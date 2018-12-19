from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
import sys
import re
from datetime import datetime
import statistics

USERNAME = '*****'
PASSWORD = '*****'

browser = webdriver.Chrome()
browser.get('http://ischool.illinois.edu')

# click login link on top right
login_link = browser.find_element_by_xpath('//a[contains(text(), "Log in to Courses") and @class="eyebrow-menu__item-link"]')
login_link.click()

# select UIUC campus login, then hit "Select"
uiuc_radio_btn = browser.find_element_by_id('urn:mace:incommon:uiuc.edu')
uiuc_radio_btn.click()
uiuc_radio_btn.submit()

# input username and password to login, can't use submit() since form has action attribute attached,
# need to manually click submit button
username_field = browser.find_element_by_id('j_username')
username_field.send_keys(USERNAME)
password_field = browser.find_element_by_id('j_password')
password_field.send_keys(PASSWORD)
submit_btn = browser.find_element_by_name('_eventId_proceed')
submit_btn.click()

# switch focus to the UI Verify iframe, which has all the 2FA options
browser.switch_to.frame(browser.find_element_by_id('duo_iframe'))

# wait up to 10 seconds for 2FA menu to fully render, then click on "Send me a push" in 2FA menu
try:
    send_push_btn = WebDriverWait(browser, 10).until(
        expected_conditions.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Send me a push")]')))
    send_push_btn.click()
except:
    print('Timed out waiting for 2FA menu to load, quitting...')
    sys.exit()

# wait up to 30 seconds for user to accept push notification on phone (use page title as indicator of login success)
login_complete = False
try:
    login_complete = WebDriverWait(browser, 30).until(
        expected_conditions.title_is('School of Information Sciences'))
except:
    print('Timed out waiting for user to authenticate push and for login to finish')
    sys.exit()

# double check that we indeed logged into the iSchool page
assert login_complete

# from this point on we can do our scraping!
#profile = browser.find_element_by_xpath('//span[contains(text(), "") and @class="usertext"]')
#profile.click()

# Enter FA18IS555A Usability Engineering class
browser.find_element_by_xpath('//a[contains(text(), "FA18IS555A Usability Engineering")]').click()

# Save this URL as the class homepage
class_homepage = browser.current_url

output_file = open('post_data.csv', 'w')
output_file.write(
    'week, discussion_id,'
    'avg_words_per_post,'
    'avg_questions_per_post,'
    'avg_images_per_post,'
    'avg_links_per_post,'
    'median_response_time,'
    'instructor_present,'
    'TA_present,'
    'unique_participants,num_posts,'
    'initial_post_author,'
    'initial_post_time,'
    'initial_post_first_50,'
    'initial_post_word_count,'
    'initial_post_question_count,'
    'initial_post_image_count,'
    'initial_post_link_count\n')

# loop through each week's forum posts (1-10)
for week_i in range(10):
    # click on link to Week X Readings forum
    browser.find_element_by_xpath('//span[contains(text(), "Forum - Week %d Readings")]' % (week_i+1)).click()

    # do processing with beautiful soup
    # 1. loop through each discussion
    idx_to_process = 0
    while True:
        discussion_link_cells = browser.find_elements_by_xpath('//td[@class="topic starter"]')
        if idx_to_process >= len(discussion_link_cells):
            break
        discussion_link_cells[idx_to_process].find_element_by_tag_name('a').click()
        # 2. in each discussion, grab all post elements via <div> tags with class attribute "forumpost"
        discussion_id = int(browser.current_url.split('=')[1])
        #print('discussion id = %s' % browser.current_url.split('=')[1])
        posts = browser.find_elements_by_xpath('//div[contains(@class, "forumpost")]')
        #print(posts)

        word_avg = 0
        question_avg = 0
        image_avg = 0
        instructor_presence = False
        TA_presence = False
        unique_participants = set()
        is_reply = False
        ext_link_avg = 0
        response_times = []
        prev_post_time = None

        initial_post_word_count = 0
        initial_post_question_count = 0
        initial_post_image_count = 0

        for i, post in enumerate(posts):
            # 3. for each post extract student name, timestamp, post text, discussion ID, is_reply and write to CSV file
            author_div = post.find_element_by_class_name('author')
            author = author_div.find_element_by_tag_name('a').text
            timestamp = author_div.text.split(' - ')[1]

            unique_participants.add(author)
            if 'Twidale' in author:
                instructor_presence = True
            elif 'Hur' in author:
                TA_presence = True

            num_links = 0
            post_content = post.find_element_by_class_name('content')
            post_paragraphs = []
            for elem in post_content.find_elements_by_tag_name('p'):
                post_paragraphs.append(elem.text.strip().replace('\"', '\"\"'))
                links = elem.find_elements_by_tag_name('a')
                num_links += len(links)

            post_text = ' '.join(post_paragraphs)
            bullet_pts =  [elem.text.strip().replace('\"', '\"\"') for elem in post_content.find_elements_by_tag_name('li')]
            post_text += ' '.join(bullet_pts)
            word_count = len(post_text.split())

            word_avg += word_count
            num_questions = re.sub(r'(\?\!*)+', '?', post_text).count('?')
            question_avg += num_questions
            ext_link_avg += num_links

            without_day = re.sub(r'.*day, ', '', timestamp)
            post_time = datetime.strptime(without_day, '%B %d, %Y, %I:%M %p')
            if prev_post_time:
                response_times.append((post_time - prev_post_time).total_seconds())
            prev_post_time = post_time

            # find all image elements, add count to image_avg
            images = post.find_elements_by_tag_name('img')
            num_images = len(images) - 1
            image_avg += num_images # subtract one for profile pictures

            if i == 0:
                initial_post_image_count = num_images
                initial_post_question_count = num_questions
                initial_post_word_count = word_count
                initial_post_link_count = num_links
                initial_post_first_50 = post_text[:50]
                initial_post_author = author
                initial_post_time = timestamp

            # print('%d, %d, %s, %s, %s' % (discussion_id, is_reply, student, timestamp, post_first_50, word_count))
            # output_file.write('%d,%d,%d,%s,"%s","%s",%d\n' % (week_i+1,discussion_id, is_reply, student, timestamp, post_text[:50], word_count))
            if not is_reply:
                is_reply = True

        num_posts = float(len(posts))
        word_avg /= num_posts
        question_avg /= num_posts
        image_avg /= num_posts
        ext_link_avg /= num_posts
        if len(response_times) == 0:
            response_time_median = -1
        else:
            response_time_median = statistics.median(response_times)
        #avg_response_time /= num_posts
        num_unique_participants = len(unique_participants)

        # write <week_#, discussion_id, avg_words_per_post, avg_questions_per_post, avg_images_per_post, avg_response_time, instructor_present, TA_present, unique_participants>
        output_file.write('%d,%d,%f,%f,%f,%f,%f,%d,%d,%d,%d,"%s","%s","%s",%d,%d,%d,%d\n' % (
            week_i+1,
            discussion_id,
            word_avg,
            question_avg,
            image_avg,
            ext_link_avg,
            response_time_median,
            instructor_presence,
            TA_presence,
            num_unique_participants,
            num_posts,
            initial_post_author,
            initial_post_time,
            initial_post_first_50,
            initial_post_word_count,
            initial_post_question_count,
            initial_post_image_count,
            initial_post_link_count)
        )

        browser.execute_script('window.history.go(-1)')
        idx_to_process += 1

    # return back to class homepage
    browser.get(class_homepage)
output_file.close()