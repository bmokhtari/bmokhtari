# Bilar Mokhtari

## Profile

Ambitious Software Engineering student at McGill University with a passion for innovative technology solutions. Experienced in full-stack development, data analysis, and machine learning applications. Skilled in Python, C++, SQL, and web technologies. Committed to continuous learning and applying cutting-edge technologies to solve real-world problems.

### Key Skills:
- Full-stack Development: Proficient in building end-to-end web applications
- Data Analysis: Experience with SQL, Python, and data visualization tools
- Machine Learning: Implemented ML models for image processing and predictive analytics
- Problem-Solving: Demonstrated ability to overcome technical challenges with creative solutions
- Collaborative: Effective team player with strong communication skills

### Code Samples:

#### Python (Data Analysis)
```python
import pandas as pd
import matplotlib.pyplot as plt

# Load and analyze rental data
df = pd.read_csv('rental_data.csv')
avg_rent = df.groupby('neighborhood')['price'].mean()

# Visualize results
plt.figure(figsize=(10, 6))
avg_rent.plot(kind='bar')
plt.title('Average Rent by Neighborhood')
plt.xlabel('Neighborhood')
plt.ylabel('Average Rent ($)')
plt.show()
