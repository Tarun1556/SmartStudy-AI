from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from app.db.session import SessionLocal
from app.models import (
    User, Course, Lecture, TranscriptSegment, LectureNote,
    Topic, TopicMention, StudyGuide, SearchDocument, ProcessingJob
)
from app.services.embeddings import get_embedding_provider
from app.core.config import get_settings

logger = logging.getLogger("studyapp")
settings = get_settings()


DEMO_COURSE_NAME = "Data Structures & Algorithms"
DEMO_LECTURES = [
    {
        "num": 1,
        "title": "Lecture 1: Introduction to Algorithms",
        "date_days_ago": 35,
        "overview": "Introduction to algorithm analysis, Big O notation, time and space complexity. Covers asymptotic analysis and why complexity matters when designing algorithms.",
        "key_ideas": [
            "Algorithms are step-by-step procedures for solving computational problems.",
            "Big O notation describes the upper bound on growth rate of a function.",
            "Common complexities include O(1), O(log n), O(n), O(n log n), O(n²), and O(2ⁿ).",
            "Space complexity measures memory usage alongside execution time.",
            "Choosing the right data structure dramatically impacts algorithm performance.",
        ],
        "definitions": [
            {"term": "Algorithm", "definition": "A finite sequence of well-defined instructions to solve a problem."},
            {"term": "Big O Notation", "definition": "Mathematical notation describing limiting behavior of a function as input grows."},
            {"term": "Time Complexity", "definition": "The computational time taken by an algorithm as a function of input size."},
            {"term": "Space Complexity", "definition": "Amount of memory an algorithm uses during execution."},
            {"term": "Asymptotic Analysis", "definition": "Analyzing algorithm behavior as input size approaches infinity."},
        ],
        "topics": ["Algorithm", "Big O Notation", "Time Complexity", "Space Complexity", "Asymptotic Analysis"],
    },
    {
        "num": 2,
        "title": "Lecture 2: Arrays & Linked Lists",
        "date_days_ago": 28,
        "overview": "Arrays and Linked Lists are the most fundamental linear data structures. Arrays offer O(1) access while linked lists provide O(1) insertions and deletions at known positions.",
        "key_ideas": [
            "Arrays store elements in contiguous memory locations enabling index-based access.",
            "Dynamic arrays resize automatically but may incur amortized costs.",
            "Singly linked lists consist of nodes with data and a next pointer.",
            "Doubly linked lists allow traversal in both directions.",
            "Choosing between arrays and linked lists depends on access patterns.",
        ],
        "definitions": [
            {"term": "Array", "definition": "Contiguous collection of same-type elements indexed by integers."},
            {"term": "Linked List", "definition": "Linear data structure of nodes connected by pointers."},
            {"term": "Dynamic Array", "definition": "Array that resizes automatically when capacity is reached."},
            {"term": "Singly Linked List", "definition": "Linked list where each node points only to the next node."},
            {"term": "Doubly Linked List", "definition": "Linked list with pointers to both previous and next nodes."},
        ],
        "topics": ["Array", "Linked List", "Dynamic Array", "Doubly Linked List", "Singly Linked List"],
    },
    {
        "num": 3,
        "title": "Lecture 3: Stacks & Queues",
        "date_days_ago": 21,
        "overview": "Stacks follow LIFO ordering (Last-In-First-Out) and Queues follow FIFO ordering (First-In-First-Out). Both are abstract data types implemented with arrays or linked lists.",
        "key_ideas": [
            "Stacks support push, pop, and peek operations in O(1) time.",
            "Queues support enqueue, dequeue, and peek operations in O(1) with proper implementation.",
            "Stacks are used for call stacks, expression evaluation, and DFS.",
            "Queues underlie scheduling systems and BFS traversal.",
            "Deques support operations on both ends combining stack and queue behavior.",
        ],
        "definitions": [
            {"term": "Stack", "definition": "LIFO abstract data type with push and pop operations from top."},
            {"term": "Queue", "definition": "FIFO abstract data type with enqueue at rear and dequeue at front."},
            {"term": "LIFO", "definition": "Last-In-First-Out ordering used by stacks."},
            {"term": "FIFO", "definition": "First-In-First-Out ordering used by queues."},
            {"term": "Deque", "definition": "Double-ended queue allowing insertion and deletion at both ends."},
        ],
        "topics": ["Stack", "Queue", "LIFO", "FIFO", "Deque", "Depth-First Search", "Breadth-First Search"],
    },
    {
        "num": 4,
        "title": "Lecture 4: Trees & Binary Search Trees",
        "date_days_ago": 14,
        "overview": "Trees are hierarchical data structures. Binary Search Trees impose ordering on nodes so lookups, insertions, and deletions run in O(log n) average time.",
        "key_ideas": [
            "A tree consists of nodes connected by edges with one distinguished root node.",
            "Binary trees have at most two children per node: left and right.",
            "BST property: left subtree keys are less than parent, right subtree keys are greater.",
            "In-order traversal of a BST yields elements in sorted order.",
            "Balanced BST variants include AVL trees and Red-Black trees.",
        ],
        "definitions": [
            {"term": "Tree", "definition": "Connected acyclic graph with hierarchical structure."},
            {"term": "Binary Tree", "definition": "Tree where each node has at most two children."},
            {"term": "Binary Search Tree (BST)", "definition": "Ordered binary tree with BST property for efficient search."},
            {"term": "Tree Traversal", "definition": "Visiting each node in a tree exactly once (pre-order, in-order, post-order, level-order)."},
            {"term": "Balanced Tree", "definition": "Tree where heights of left and right subtrees differ by at most a constant."},
        ],
        "topics": ["Tree", "Binary Tree", "Binary Search Tree", "BST", "Tree Traversal", "Balanced Tree"],
    },
    {
        "num": 5,
        "title": "Lecture 5: Hash Tables & Hashing",
        "date_days_ago": 7,
        "overview": "Hash tables map keys to values using a hash function. With good hashing and collision resolution, average case operations are O(1), making hash tables among the most useful data structures.",
        "key_ideas": [
            "A hash function transforms a key into an array index.",
            "Collisions occur when two keys hash to the same index.",
            "Chaining and open addressing are common collision resolution strategies.",
            "Load factor is the ratio of stored entries to table size.",
            "Rehashing rebuilds a larger table when load factor exceeds a threshold.",
        ],
        "definitions": [
            {"term": "Hash Table", "definition": "Data structure mapping keys to values via a hash function."},
            {"term": "Hash Function", "definition": "Function converting a key into a table index."},
            {"term": "Collision", "definition": "Event when two distinct keys produce the same hash index."},
            {"term": "Chaining", "definition": "Collision resolution storing multiple entries in a linked list per bucket."},
            {"term": "Load Factor", "definition": "Ratio of entries to table capacity; triggers resizing when high."},
        ],
        "topics": ["Hash Table", "Hash Function", "Collision", "Chaining", "Load Factor", "Open Addressing"],
    },
    {
        "num": 6,
        "title": "Lecture 6: Graphs & Graph Algorithms",
        "date_days_ago": 2,
        "overview": "Graphs model pairwise relationships using vertices and edges. BFS explores nodes level-by-level while DFS goes deep first. Shortest paths and spanning trees are classic graph problems.",
        "key_ideas": [
            "A graph G = (V, E) consists of a vertex set V and edge set E.",
            "Graphs are represented as adjacency lists or adjacency matrices.",
            "BFS finds shortest paths in unweighted graphs in O(V+E) time.",
            "DFS is useful for cycle detection, topological sort, and connectivity.",
            "Dijkstra's algorithm computes single-source shortest paths in weighted graphs with non-negative weights.",
        ],
        "definitions": [
            {"term": "Graph", "definition": "Set of vertices connected by edges modeling relationships."},
            {"term": "BFS", "definition": "Breadth-First Search exploring nodes level by level using a queue."},
            {"term": "DFS", "definition": "Depth-First Search traversing as deep as possible before backtracking."},
            {"term": "Adjacency List", "definition": "Graph representation storing neighbors per vertex."},
            {"term": "Dijkstra's Algorithm", "definition": "Algorithm for shortest paths from single source with non-negative weights."},
        ],
        "topics": ["Graph", "BFS", "DFS", "Dijkstra's Algorithm", "Adjacency List", "Shortest Path", "Breadth-First Search", "Depth-First Search"],
    },
]

CROSS_TOPICS = {
    "Time Complexity": [1, 2, 3, 4, 5, 6],
    "Big O Notation": [1, 2, 3, 4, 5, 6],
    "Algorithm": [1, 3, 4, 5, 6],
    "Array": [2, 3, 5],
    "Linked List": [2, 3],
    "Stack": [3, 4, 6],
    "Queue": [3, 6],
    "BFS": [3, 6],
    "DFS": [3, 6],
    "Tree": [4, 6],
    "Binary Search Tree": [4],
    "BST": [4],
    "Hash Table": [5],
    "Graph": [6],
    "Dijkstra's Algorithm": [6],
}


def _seed_user(db: Session) -> None:
    user = db.query(User).filter(User.id == 0).first()
    if not user:
        user = User(
            id=0,
            email="demo@example.com",
            full_name="Demo User",
            hashed_password="__demo__",
            is_demo=True,
        )
        db.add(user)
        db.flush()


def _seed_course(db: Session) -> Course:
    course = db.query(Course).filter(Course.user_id == 0, Course.name == DEMO_COURSE_NAME).first()
    if course:
        return course
    course = Course(
        user_id=0,
        name=DEMO_COURSE_NAME,
        description="A semester-long introduction to core data structures and algorithms including arrays, linked lists, trees, hashing, and graphs.",
        color="#4338ca",
    )
    db.add(course)
    db.flush()
    return course


def _seed_lectures(db: Session, course: Course) -> dict:
    existing = {l.lecture_number: l for l in db.query(Lecture).filter(Lecture.course_id == course.id).all()}
    out = {}
    for spec in DEMO_LECTURES:
        num = spec["num"]
        if num in existing:
            out[num] = existing[num]
            continue
        date = datetime.utcnow() - timedelta(days=spec["date_days_ago"])
        lecture = Lecture(
            course_id=course.id,
            title=spec["title"],
            lecture_number=num,
            lecture_date=date,
            description=spec["overview"],
            status="processed",
        )
        db.add(lecture)
        db.flush()
        out[num] = lecture

        for i, idea in enumerate(spec["key_ideas"]):
            seg = TranscriptSegment(
                lecture_id=lecture.id,
                segment_index=i,
                text=idea,
                start_time=None,
                end_time=None,
                source_type="text",
            )
            db.add(seg)

        job = ProcessingJob(
            lecture_id=lecture.id,
            job_type="full_processing",
            status="completed",
            current_step="Done",
            progress=100,
            started_at=date + timedelta(minutes=1),
            completed_at=date + timedelta(minutes=6),
        )
        db.add(job)
    db.flush()
    return out


def _seed_notes(db: Session, lectures: dict, specs: list) -> None:
    for spec in specs:
        num = spec["num"]
        lecture = lectures[num]
        existing = db.query(LectureNote).filter(LectureNote.lecture_id == lecture.id).first()
        if existing:
            continue
        headings = [
            {"id": f"h{num}_1", "text": f"Overview of {spec['title']}", "children": []},
            {"id": f"h{num}_2", "text": "Key Ideas", "children": []},
            {"id": f"h{num}_3", "text": "Definitions", "children": []},
        ]
        key_ideas = [{"id": f"k{num}_{i+1}", "idea": k, "source_ref": f"segment_{i}"} for i, k in enumerate(spec["key_ideas"])]
        definitions = [{"term": d["term"], "definition": d["definition"], "source_ref": f"def_{i}"} for i, d in enumerate(spec["definitions"])]
        examples = []
        note = LectureNote(
            lecture_id=lecture.id,
            title=spec["title"],
            overview=spec["overview"],
            headings=headings,
            key_ideas=key_ideas,
            definitions=definitions,
            examples=examples,
            relationships=[],
            source_references=[],
            raw_content=spec["overview"] + "\n" + "\n".join(spec["key_ideas"]),
        )
        db.add(note)
    db.flush()


def _seed_topics(db: Session, course: Course, lectures: dict, specs: list) -> None:
    existing_count = db.query(Topic).filter(Topic.course_id == course.id).count()
    if existing_count > 0:
        return

    emb_provider = get_embedding_provider()
    topic_map: dict[str, Topic] = {}

    all_topic_names = set()
    for spec in specs:
        for t in spec["topics"]:
            all_topic_names.add(t)
    for t in CROSS_TOPICS.keys():
        all_topic_names.add(t)

    text_list = [t + " computer science data structures algorithms" for t in all_topic_names]
    embeddings = emb_provider.embed_texts(text_list)
    emb_map = dict(zip(all_topic_names, embeddings))

    topic_specs = {}
    for spec in specs:
        for i, d in enumerate(spec["definitions"]):
            topic_specs[d["term"]] = {
                "description": d["definition"],
                "aliases": [d["term"]],
            }

    for name in sorted(all_topic_names):
        spec = topic_specs.get(name, {})
        topic = Topic(
            course_id=course.id,
            name=name,
            canonical_name=name,
            description=spec.get("description", f"{name} is a key concept in data structures and algorithms."),
            aliases=spec.get("aliases", [name]),
            coverage_score=0.0,
            lecture_count=0,
            evidence_count=0,
            embedding=emb_map.get(name),
            related_topics=[],
        )
        db.add(topic)
        db.flush()
        topic_map[name] = topic

    mentioned_by_lecture: dict[int, set] = {spec["num"]: set() for spec in specs}
    spec_by_num = {spec["num"]: spec for spec in specs}

    for spec in specs:
        num = spec["num"]
        lecture = lectures[num]
        mentioned_here = mentioned_by_lecture[num]
        for i, d in enumerate(spec["definitions"]):
            tname = d["term"]
            if tname in topic_map and tname not in mentioned_here:
                mentioned_here.add(tname)
                tm = TopicMention(
                    topic_id=topic_map[tname].id,
                    lecture_id=lecture.id,
                    transcript_segment_id=None,
                    context=d["definition"][:400],
                    start_time=None,
                    source_type="notes",
                    confidence=0.95,
                )
                db.add(tm)

        for i, ki in enumerate(spec["key_ideas"]):
            for tname in spec["topics"]:
                low = tname.lower()
                if low in ki.lower() and tname in topic_map and tname not in mentioned_here:
                    mentioned_here.add(tname)
                    tm = TopicMention(
                        topic_id=topic_map[tname].id,
                        lecture_id=lecture.id,
                        transcript_segment_id=None,
                        context=ki,
                        start_time=None,
                        source_type="notes",
                        confidence=0.85,
                    )
                    db.add(tm)

    # CROSS_TOPICS declares which lectures a topic recurs across (e.g. "Time
    # Complexity" spans lectures 1-6), but the passes above only ever create a
    # mention in the lecture that originally defines/names-drops a term — so
    # every topic ended up with lecture_count=1 and the demo's flagship
    # "Appears in N of M lectures" recurrence signal was always empty. Fill in
    # a mention for every (topic, lecture) pair CROSS_TOPICS actually declares,
    # using that lecture's own key ideas/overview as the supporting context.
    for tname, lecture_nums in CROSS_TOPICS.items():
        if tname not in topic_map:
            continue
        for num in lecture_nums:
            mentioned_here = mentioned_by_lecture.get(num)
            if mentioned_here is None or tname in mentioned_here:
                continue
            spec = spec_by_num[num]
            lecture = lectures[num]
            low = tname.lower()
            context = next((ki for ki in spec["key_ideas"] if low in ki.lower()), None)
            if not context:
                context = next(
                    (d["definition"] for d in spec["definitions"] if d["term"].lower() == low),
                    spec["overview"],
                )
            mentioned_here.add(tname)
            db.add(TopicMention(
                topic_id=topic_map[tname].id,
                lecture_id=lecture.id,
                transcript_segment_id=None,
                context=context[:400],
                start_time=None,
                source_type="notes",
                confidence=0.75,
            ))

    db.flush()

    from app.services.topics import recalculate_topic_stats, find_related_topics
    recalculate_topic_stats(db, course.id)

    for topic in topic_map.values():
        db.refresh(topic)


def _seed_search_index(db: Session, course: Course, lectures: dict, specs: list) -> None:
    existing = db.query(SearchDocument).filter(SearchDocument.course_id == course.id).count()
    if existing > 0:
        return
    emb_provider = get_embedding_provider()
    for spec in specs:
        num = spec["num"]
        lecture = lectures[num]
        for i, ki in enumerate(spec["key_ideas"]):
            emb = emb_provider.embed_texts([f"{spec['title']} {ki}"])[0]
            db.add(SearchDocument(
                course_id=course.id,
                lecture_id=lecture.id,
                doc_type="segment",
                title=f"{spec['title']} — Idea {i+1}",
                content=ki,
                snippet=ki[:300],
                embedding=emb,
                doc_metadata={"lecture_number": num},
            ))
        for d in spec["definitions"]:
            content = f"{d['term']}: {d['definition']}"
            emb = emb_provider.embed_texts([content])[0]
            db.add(SearchDocument(
                course_id=course.id,
                lecture_id=lecture.id,
                doc_type="topic",
                title=f"Definition: {d['term']}",
                content=content,
                snippet=content[:300],
                embedding=emb,
                doc_metadata={"term": d["term"], "lecture_number": num},
            ))
    db.flush()


def _seed_study_guide(db: Session, course: Course) -> None:
    existing = db.query(StudyGuide).filter(StudyGuide.course_id == course.id).count()
    if existing > 0:
        return

    from app.services.study_guide import generate_study_guide
    try:
        generate_study_guide(db, course.id)
    except Exception as e:
        logger.warning(f"Study guide seed skipped: {e}")


def ensure_demo_seeded() -> None:
    db = SessionLocal()
    try:
        _seed_user(db)
        course = _seed_course(db)
        lectures = _seed_lectures(db, course)
        _seed_notes(db, lectures, DEMO_LECTURES)
        _seed_topics(db, course, lectures, DEMO_LECTURES)
        _seed_search_index(db, course, lectures, DEMO_LECTURES)
        _seed_study_guide(db, course)
        db.commit()
        logger.info("Demo seeding complete")
    except Exception as e:
        logger.exception(f"Demo seeding failed: {e}")
        db.rollback()
    finally:
        db.close()
