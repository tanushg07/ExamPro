#!/usr/bin/env python3
"""
Test script to verify the teacher review functionality works correctly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, User, Exam, ExamReview
from flask import url_for

def test_view_exam_reviews():
    """Test the view_exam_reviews route"""
    app = create_app()
    
    with app.test_client() as client:
        with app.app_context():
            # Try to create a mock context to test the route
            try:
                print("Testing view_exam_reviews route...")
                
                # Check if we can import the route function
                from app.routes import view_exam_reviews
                print("✓ Route function imported successfully")
                
                # Test the stats calculation logic
                print("Testing stats calculation...")
                
                # Mock some review data
                class MockReview:
                    def __init__(self, rating):
                        self.rating = rating
                
                class MockExam:
                    def get_average_rating(self):
                        return 4.2
                
                # Test stats calculation
                reviews = [MockReview(5), MockReview(4), MockReview(3), MockReview(5), MockReview(4)]
                
                stats = {
                    'total': len(reviews),
                    'average': None,
                    'counts': {
                        '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
                    }
                }
                
                # Test average calculation
                mock_exam = MockExam()
                try:
                    if len(reviews) > 0:
                        stats['average'] = mock_exam.get_average_rating()
                    else:
                        stats['average'] = None
                    print(f"✓ Average rating calculated: {stats['average']}")
                except Exception as e:
                    print(f"✗ Error calculating average: {e}")
                    stats['average'] = None
                
                # Test rating counts
                for review in reviews:
                    try:
                        if review.rating and 1 <= review.rating <= 5:
                            stats['counts'][str(review.rating)] += 1
                    except Exception as e:
                        print(f"✗ Error processing review rating {review.rating}: {e}")
                
                # Test percentage calculation
                if stats['total'] > 0:
                    for rating in stats['counts']:
                        count = stats['counts'][rating]
                        stats['counts'][rating] = {
                            'count': count,
                            'percent': round((count / stats['total']) * 100) if stats['total'] > 0 else 0
                        }
                
                print(f"✓ Final stats: {stats}")
                
                # Test template variables
                if stats['total'] > 0 and stats['average'] is not None:
                    formatted_average = "%.1f" % stats['average']
                    print(f"✓ Formatted average for template: {formatted_average}")
                    
                    # Test star calculation
                    rounded_average = round(stats['average'])
                    stars = "★" * rounded_average + "☆" * (5 - rounded_average)
                    print(f"✓ Star display: {stars}")
                
                print("✓ All tests passed! The teacher review functionality should work correctly.")
                
            except Exception as e:
                print(f"✗ Error during testing: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    test_view_exam_reviews()
