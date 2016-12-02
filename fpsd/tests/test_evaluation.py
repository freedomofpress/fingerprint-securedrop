import unittest

from evaluation import precision_recall_at_x_proportion


class EvaluationTest(unittest.TestCase):
    """Most evaluation methods are from scikit-learn and are thus tested
    however some of our preprocessing is custom and should be tested"""

    def test_precision_recall_f1_perfect(self):
        test_labels = [1, 1, 0, 0]
        test_predictions = [0.99, 0.99, 0.01, 0.01]
        precision, recall, f1 = precision_recall_at_x_proportion(test_labels,
            test_predictions, x_proportion=0.50)
        self.assertEqual(recall, 1)
        self.assertEqual(precision, 1)
        self.assertEqual(f1, 1)

    def test_precision_recall_f1_horrible(self):
        test_labels = [0, 0, 1, 1]
        test_predictions = [0.99, 0.99, 0.01, 0.01]
        precision, recall, f1 = precision_recall_at_x_proportion(test_labels,
            test_predictions, x_proportion=0.50)
        self.assertEqual(recall, 0)
        self.assertEqual(precision, 0)
        self.assertEqual(f1, 0)

    def test_precision_recall_f1_realistic(self):
        test_labels = [1, 0, 1, 0]
        test_predictions = [0.80, 0.20, 0.20, 0.80]
        precision, recall, f1 = precision_recall_at_x_proportion(test_labels,
            test_predictions, x_proportion=0.50)
        self.assertEqual(recall, 0.5)
        self.assertEqual(precision, 0.5)
        self.assertEqual(f1, 0.5)


if __name__ == "__main__":
    unittest.main()
