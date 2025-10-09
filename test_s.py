#!/usr/bin/env python3
import unittest
from unittest.mock import patch, mock_open, MagicMock
import sys
import os

# Import the module under test
import s

class TestS(unittest.TestCase):

    def test_parse_maps_line_valid(self):
        """Test parsing a valid maps line"""
        line = "7ffff7dd4000-7ffff7dfc000 r-xp 00000000 08:01 1234567 /lib/x86_64-linux-gnu/libc-2.31.so"
        result = s.parse_maps_line(line)
        self.assertIsNotNone(result)
        start, end, perms = result
        self.assertEqual(start, 0x7ffff7dd4000)
        self.assertEqual(end, 0x7ffff7dfc000)
        self.assertEqual(perms, "r-xp")

    def test_parse_maps_line_invalid(self):
        """Test parsing an invalid maps line"""
        line = "invalid line format"
        result = s.parse_maps_line(line)
        self.assertIsNone(result)

    def test_parse_maps_line_different_perms(self):
        """Test parsing maps line with different permissions"""
        line = "7ffff7dd4000-7ffff7dfc000 rwx- 00000000 08:01 1234567"
        result = s.parse_maps_line(line)
        self.assertIsNotNone(result)
        start, end, perms = result
        self.assertEqual(perms, "rwx-")

    @patch('s.open', new_callable=mock_open, read_data="invalid line\n")
    def test_read_memory_regions_invalid_maps(self, mock_file):
        """Test read_memory_regions with invalid maps data"""
        pid = 1234
        regions = list(s.read_memory_regions(pid, do_ptrace=False))
        self.assertEqual(len(regions), 0)

    def test_ptrace_error_creation(self):
        """Test PtraceError exception creation"""
        error = s.PtraceError("Test error")
        self.assertEqual(str(error), "Test error")
        self.assertIsInstance(error, Exception)

    @patch('sys.argv', ['s.py', '1234'])
    @patch('s.read_memory_regions')
    @patch('sys.stdout.buffer.write')
    def test_main_basic_usage(self, mock_write, mock_read_regions):
        """Test main function with basic usage"""
        mock_read_regions.return_value = [(0x1000, 0x2000, b"test_data")]

        result = s.main()
        self.assertEqual(result, 0)
        mock_read_regions.assert_called_once_with(1234, do_ptrace=False)
        mock_write.assert_called_once_with(b"test_data")

    @patch('sys.argv', ['s.py'])
    def test_main_no_args(self):
        """Test main function with no arguments"""
        with patch('builtins.print') as mock_print:
            result = s.main()
            self.assertEqual(result, 2)
            mock_print.assert_called_once()

    @patch('sys.argv', ['s.py', '1234', '--ptrace'])
    @patch('s.read_memory_regions')
    @patch('sys.stdout.buffer.write')
    def test_main_with_ptrace(self, mock_write, mock_read_regions):
        """Test main function with ptrace option"""
        mock_read_regions.return_value = [(0x1000, 0x2000, b"test_data")]

        result = s.main()
        self.assertEqual(result, 0)
        mock_read_regions.assert_called_once_with(1234, do_ptrace=True)

    @patch('sys.argv', ['s.py', '1234', '-o', 'output.bin'])
    @patch('s.read_memory_regions')
    @patch('builtins.open', new_callable=mock_open)
    def test_main_with_output_file(self, mock_file, mock_read_regions):
        """Test main function with output file option"""
        mock_read_regions.return_value = [(0x1000, 0x2000, b"test_data")]

        result = s.main()
        self.assertEqual(result, 0)
        mock_file.assert_called_once_with('output.bin', 'wb')
        mock_file().write.assert_called_once_with(b"test_data")

    @patch('sys.argv', ['s.py', '1234', '-o'])
    def test_main_output_file_no_name(self):
        """Test main function with -o but no filename"""
        with patch('builtins.print') as mock_print:
            result = s.main()
            self.assertEqual(result, 2)
            mock_print.assert_called_once_with("Error: -o parameter requires a filename")

if __name__ == '__main__':
    unittest.main()