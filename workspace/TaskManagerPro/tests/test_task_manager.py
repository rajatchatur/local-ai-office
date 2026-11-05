import unittest

from task_manager import TaskManager

class TestTaskManager(unittest.TestCase):
    def test_add_task(self):
        manager = TaskManager()
        with tempfile.TemporaryDirectory() as tmpdir:
            manager_path = tmpdir.path
            manager.save_tasks(manager_path)
            self.assertEqual(len(manager.tasks), 1)
            self.assertEqual(manager.tasks[0].title, 'Test Task')

    def test_add_empty_task(self):
        manager = TaskManager()
        with tempfile.TemporaryDirectory() as tmpdir:
            manager_path = tmpdir.path
            manager.save_tasks(manager_path)
            self.assertRaises(ValueError, manager.add_task, '')

    def test_mark_complete(self):
        manager = TaskManager()
        with tempfile.TemporaryDirectory() as tmpdir:
            manager_path = tmpdir.path
            manager.save_tasks(manager_path)
            manager.add_task('Test Task')
            self.assertTrue(manager.mark_complete(1))
            self.assertTrue(manager.tasks[0].completed)

    def test_delete_task(self):
        manager = TaskManager()
        with tempfile.TemporaryDirectory() as tmpdir:
            manager_path = tmpdir.path
            manager.save_tasks(manager_path)
            manager.add_task('Test Task')
            self.assertTrue(manager.delete_task(1))
            self.assertEqual(len(manager.tasks), 0)