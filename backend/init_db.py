from backend.app.database import init_db, SessionLocal
from backend.app import models, auth


STUDENTS = [
    ("24071A6601", "Aarav Sharma"),
    ("24071A6602", "Vivaan Reddy"),
    ("24071A6603", "Aditya Verma"),
    ("24071A6604", "Arjun Nair"),
    ("24071A6605", "Sai Kiran"),
    ("24071A6606", "Rahul Mehta"),
    ("24071A6607", "Karthik Iyer"),
    ("24071A6608", "Rohit Kumar"),
    ("24071A6609", "Ankit Gupta"),
    ("24071A6610", "Harsha Vardhan"),
    ("24071A6611", "Nikhil Jain"),
    ("24071A6612", "Sandeep Yadav"),
    ("24071A6613", "Abhishek Singh"),
    ("24071A6614", "Varun Teja"),
    ("24071A6615", "Manish Patel"),
    ("24071A6616", "Pranav Kulkarni"),
    ("24071A6617", "Deepak Mishra"),
    ("24071A6618", "Naveen Babu"),
    ("24071A6619", "Tarun Joshi"),
    ("24071A6620", "Yash Agarwal"),
    ("24071A6621", "Akash Choudhary"),
    ("24071A6622", "Rohan Das"),
    ("24071A6623", "Shubham Tiwari"),
    ("24071A6624", "Gaurav Saxena"),
    ("24071A6625", "Mohit Bansal"),
    ("24071A6626", "Piyush Arora"),
    ("24071A6627", "Siddharth Roy"),
    ("24071A6628", "Vikas Pandey"),
    ("24071A6629", "Ajay Thakur"),
    ("24071A6630", "Himanshu Raj"),
    ("24071A6631", "Lokesh Kumar"),
    ("24071A6632", "Suraj Patil"),
    ("24071A6633", "Vinay Shetty"),
    ("24071A6634", "Tejas Gowda"),
    ("24071A6635", "Ritesh Chauhan"),
    ("24071A6636", "Kunal Sinha"),
    ("24071A6637", "Neeraj Singh"),
    ("24071A6638", "Amarjeet Singh"),
    ("24071A6639", "Bharat Solanki"),
    ("24071A6640", "Chandan Roy"),
    ("24071A6641", "Dinesh Yadav"),
    ("24071A6642", "Eshwar Reddy"),
    ("24071A6643", "Faizan Ali"),
    ("24071A6644", "Ganesh Naik"),
    ("24071A6645", "Hitesh Parmar"),
    ("24071A6646", "Imran Khan"),
    ("24071A6647", "Jatin Malhotra"),
    ("24071A6648", "Kiran Kumar"),
    ("24071A6649", "Lalit Verma"),
    ("24071A6650", "Mahesh Babu"),
    ("24071A6651", "Nitesh Kumar"),
    ("24071A6652", "Omkar Patil"),
    ("24071A6653", "Pradeep Kumar"),
    ("24071A6654", "Qasim Ali"),
    ("24071A6655", "Rakesh Sharma"),
    ("24071A6656", "Sanjay Das"),
    ("24071A6657", "Tushar Gupta"),
    ("24071A6658", "Uday Singh"),
    ("24071A6659", "Vijay Kumar"),
    ("24071A6660", "Wasim Akram"),
    ("24071A6661", "Xavior Dsouza"),
    ("24071A6662", "Yogesh Patil"),
    ("24071A6663", "Zaid Khan"),
    ("24071A6664", "Arvind Rao"),
    ("24071A6665", "Bhavesh Shah"),
    ("24071A6666", "Chetan Desai"),
    ("24071A6667", "Devendra Singh"),
    ("24071A6668", "Farhan Sheikh"),
    ("24071A6669", "Gokul Krishnan"),
]

SPECIAL_USERS = [
    {"username": "maintainer", "password": "changeme", "role": "maintainer"},
    {"username": "coordinator", "password": "changeme", "role": "coordinator"},
    {"username": "teacher", "password": "changeme", "role": "teacher"},
    {"username": "student_test", "password": "changeme", "role": "student"},
]

LEGACY_TEACHERS = [
    {"name": "Dr. Pooja Mehta", "email": "pooja.mehta@edu.in", "password": "Edu@123"},  # SE
    {"name": "Dr. Priya Sharma", "email": "priya.sharma@edu.in", "password": "Edu@123"},  # DBMS
    {"name": "Dr. Ravi Verma", "email": "ravi.verma@edu.in", "password": "Edu@123"},  # OS
    {"name": "Dr. Sneha Reddy", "email": "sneha.reddy@edu.in", "password": "Edu@123"},  # CN
    {"name": "Dr. Kiran Rao", "email": "kiran.rao@edu.in", "password": "Edu@123"},  # ACD
    {"name": "Dr. Meena Iyer", "email": "meena.iyer@edu.in", "password": "Edu@123"},  # ML
    {"name": "Ms. Kavya Iyer", "email": "kavya.iyer@edu.in", "password": "Edu@123"},  # SIMA
    {"name": "Mr. Arjun Singh", "email": "arjun.singh@edu.in", "password": "Edu@123"},  # LAB
    {"name": "Mr. Manish Yadav", "email": "manish.yadav@edu.in", "password": "Edu@123"},  # SPORTS
]

def add_user(db, username, password, role):
    user = models.User(username=username, password_hash=auth.get_password_hash(password), role=role)
    db.add(user)
    db.flush()
    return user


def main():
    init_db()
    db = SessionLocal()
    try:
        # wipe previous users/students/teachers/subjects/timetable/attendance for a clean seed
        db.query(models.AttendanceRecord).delete()
        db.query(models.Letter).delete()
        db.query(models.Timetable).delete()
        db.query(models.Subject).delete()
        db.query(models.Teacher).delete()
        db.query(models.Student).delete()
        db.query(models.User).delete()
        db.commit()

        # create default accounts expected by the docs/scripts
        special_users = {}
        for account in SPECIAL_USERS:
            user = add_user(db, account["username"], account["password"], account["role"])
            special_users[account["username"]] = user
        # keep the generic teacher account for demo scripts; map it to a valid sample subject teacher
        db.add(models.Teacher(name="Dr. Pooja Mehta", user_id=special_users["teacher"].id))

        # create legacy teacher users and teacher rows used by the current local demo
        for t in LEGACY_TEACHERS:
            u = add_user(db, t["email"], t["password"], "teacher")
            teacher = models.Teacher(name=t["name"], user_id=u.id)
            db.add(teacher)
        db.commit()

        # create student users and student rows
        for roll, name in STUDENTS:
            email = f"{roll.lower()}@edu.in"
            u = add_user(db, email, "Edu@123", "student")
            s = models.Student(roll_number=roll, name=name, user_id=u.id)
            db.add(s)
        db.commit()

        # link the generic student_test account to the first seeded student
        first_student = db.query(models.Student).filter_by(roll_number="24071A6601").first()
        if first_student:
            test_user = db.query(models.User).filter_by(username="student_test").first()
            if test_user:
                first_student.user_id = test_user.id
                db.commit()

        print(f"DB initialized and seeded: {len(STUDENTS)} students, {len(LEGACY_TEACHERS) + 1} teacher accounts plus default roles.")
    finally:
        db.close()


if __name__ == '__main__':
    main()
