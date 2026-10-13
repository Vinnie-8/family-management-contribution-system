# ==Normal Forms in DBMS==



Normal forms are a set of progressive rules (or design checkpoints) for relational schemas that reduce redundancy and prevent data anomalies. Each normal form ( 1NF, 2NF, 3NF, BCNF, 4NF, 5NF ) is stricter than the previous one: meeting a higher normal form implies the lower ones are satisfied. Think of them as layers of cleanliness for your tables: the deeper you go, the fewer redundancy and integrity problems you’ll have.

## ==Benefits of using Normal Forms==

- Reduce duplicate data and wasted storage.
- Prevent insert, update, and delete anomalies.
- Improve data consistency and integrity.
- Make the schema easier to maintain and evolve.

!!! example
   - Let's break down the various normal forms step-by-step to understand the conditions that need to be satisfied at each level:

## TYPES OF NORMAL FORMS

1. **First Normal Form (1NF): Eliminating Duplicate Records**

A table is in 1NF if it satisfies the following conditions:

- All columns contain atomic values (i.e., indivisible values).
- Each row is unique (i.e., no duplicate rows).
- Each column has a unique name.
- The order in which data is stored does not matter.

!!! example
    1NF Violation: If a table has a column "Phone Numbers" that stores multiple phone numbers in a single cell, it violates 1NF. To bring it into 1NF, you need to separate phone numbers into individual rows.

2. **Second Normal Form (2NF): Eliminating Partial Dependency**

A relation is in 2NF if it satisfies the conditions of 1NF and additionally, contains no partial dependency exists, meaning every non-prime attribute (non-key attribute) must depend on the entire primary key, not just a part of it.

!!! example
    For a composite key (StudentID, CourseID), if the "StudentName" depends only on "StudentID" and not on the entire key, it violates 2NF. To normalize, move StudentName into a separate table where it depends only on "StudentID"

3. **Third Normal Form (3NF): Eliminating Transitive Dependency**

A relation is in 3NF if it satisfies 2NF and additionally, there are no transitive dependencies. In simpler terms, non-prime attributes should not depend on other non-prime attributes.

!!! example
    Consider a table with (StudentID, CourseID, Instructor). If Instructor depends on "CourseID", and "CourseID" depends on "StudentID", then Instructor indirectly depends on "StudentID", which violates 3NF. To resolve this, place Instructor in a separate table linked by "CourseID".

4. **Boyce-Codd Normal Form (BCNF): The Strongest Form of 3NF**

BCNF is a stricter version of 3NF where for every non-trivial functional dependency (X → Y), X must be a superkey (a unique identifier for a record in the table).

!!! example 
    If a table has a dependency (StudentID, CourseID) → Instructor, but neither "StudentID" nor "CourseID" is a superkey, then it violates BCNF. To bring it into BCNF, decompose the table so that each determinant is a candidate key.

5. **Fourth Normal Form (4NF): Removing Multi-Valued Dependencies**

A table is in 4NF if it is in BCNF and has no multi-valued dependencies. A multi-valued dependency occurs when one attribute determines another, and both attributes are independent of all other attributes in the table.

!!! example 
    Consider a table where (StudentID, Language, Hobby) are attributes. If a student can have multiple hobbies and languages, a multi-valued dependency exists. To resolve this, split the table into separate tables for Languages and Hobbies.

6. **Fifth Normal Form (5NF): Eliminating Join Dependency**

5NF is achieved when a table is in 4NF and all join dependencies are removed. This form ensures that every table is fully decomposed into smaller tables that are logically connected without losing information.

!!! example 
    If a table contains (StudentID, Course, Instructor) and there is a dependency where all combinations of these columns are needed for a specific relationship, you would split them into smaller tables to remove redundancy.

## Common Challenges of Over-Normalization

While normalization is a powerful tool for optimizing databases, it's important not to over-normalize your data.

Excessive normalization can lead to:

- Complex Queries: Too many tables may result in multiple joins, making queries slow and difficult to manage.

- Performance Overhead: Additional processing required for joins in overly normalized databases may hurt performance, especially in large-scale systems.

In many cases, **denormalization (combining tables to reduce the need for complex joins)** is used for performance optimization in specific applications, such as reporting systems.

## When to Use Normalization and Denormalization

**Normalization** is best suited for transactional systems where data integrity is paramount, such as banking systems and enterprise applications.

**Denormalization** is ideal for read-heavy applications like data warehousing and reporting systems where performance and query speed are more critical than data integrity.

## ==When Normalization is Not Followed==

Rules of database normalization are intentionally skipped or broken—a process known as denormalization—when strict table separation hurts system performance or speed.

- **Read-Heavy Workloads:** 

    When an application reads data much more often than it writes (such as a public-facing catalog or dashboard), joining dozens of normalized tables slows down query response times. Users on Stack Overflow generally agree that denormalizing helps avoid excessive and costly JOIN operations.
 
- **Data Warehouses and Reporting:** 

    Analytical systems, business intelligence tools, and OLAP (Online Analytical Processing) cubes store pre-aggregated or redundant data (like star or snowflake schemas with materialized views) to speed up complex historical reporting.

- **High-Performance / Low-Latency Systems:** 

    When real-time gaming, high-frequency trading, or large-scale web services cannot afford the CPU overhead of stitching together scattered rows across multiple tables, data is duplicated.

- **Prototyping and Early Development:** 
    
    During fast iteration, small projects, or simple schemas, rigid normalization adds unnecessary design and coding complexity before performance bottlenecks even exist.

- **Archival and Snapshots:** 

    Storing historical snapshots (such as freezing a customer's billing address on an old invoice) intentionally breaks normalization so past records do not change if the live user record updates.


## ==The Risks of Breaking Normalization==

When you bypass normalization, you accept trade-offs that your application code must manage:

- Data Anomalies: 

    Increased risk of update, insertion, and deletion anomalies where duplicate data falls out of sync.

- Higher Maintenance: 

    You often need extra logic, background jobs, or database triggers to keep redundant data consistent.

## References

[Normal forms](https://www.geeksforgeeks.org/dbms/normal-forms-in-dbms/)

[Watch video about normal forms](https://www.youtube.com/watch?v=J-drts33N8g)

[Different types of normal forms](https://www.youtube.com/watch?v=GFQaEYEc8_8&t=71s)

[DBMS Normal Forms](https://www.youtube.com/watch?v=IBEuwmYsMKI)

[Breaking Normalization Rules](https://stackoverflow.com/questions/2065227/when-is-a-good-time-to-break-normalization-rules?__cf_chl_tk=IdSw2iKzuoCgq.Rqz0BGxucV14cMpZfXTcv9wQnBpms-1791360275-1.0.1.1-SVJnCP8Cs6ziszMlKVW63AUM_cJEgn2gVNlLdIoAyWM)

[When normalization is not needed](https://www.quora.com/How-can-you-determine-when-is-normalization-not-needed)



