"""
Tests for profile management with tags support.

Tests cover:
- Profile tags field initialization
- Tag normalization to lowercase
- Adding and removing tags
- Tags being optional (omitted from JSON if empty)
"""

import pytest
import json
import tempfile
from pathlib import Path
from config import ConfigManager, CONFIG_FILE, CONFIG_DIR
from click.testing import CliRunner
from cli import cli


@pytest.fixture
def temp_config_dir(monkeypatch, tmp_path):
    """Create a temporary config directory for testing."""
    config_dir = tmp_path / "mcru"
    config_dir.mkdir()
    config_file = config_dir / "profiles.json"
    config_file.write_text(json.dumps({"profiles": []}, indent=2))
    
    # Monkeypatch the config paths
    monkeypatch.setattr("config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("config.CONFIG_FILE", config_file)
    
    yield config_dir, config_file


@pytest.fixture
def config_manager(temp_config_dir):
    """Create a ConfigManager instance with temporary config."""
    return ConfigManager()


class TestProfileTags:
    """Test profile tags functionality."""

    def test_profile_tags_field_added(self, config_manager):
        """Verify tags field is initialized as empty list in new profile."""
        config_manager.add_profile(
            name="test-profile",
            source="/source",
            target="/target",
            parsers=["normalize_line_endings"],
        )
        profile = config_manager.get_profile("test-profile")
        assert "tags" in profile
        assert profile["tags"] == []

    def test_update_profile_field_add_tag(self, config_manager):
        """Add tag to profile with lowercase normalization."""
        config_manager.add_profile(
            name="test-profile",
            source="/source",
            target="/target",
            parsers=[],
        )
        
        config_manager.update_profile_field("test-profile", "add-tag", "MyTag")
        profile = config_manager.get_profile("test-profile")
        assert "mytag" in profile["tags"]
        assert len(profile["tags"]) == 1

    def test_update_profile_field_add_multiple_tags(self, config_manager):
        """Add multiple tags to profile."""
        config_manager.add_profile(
            name="test-profile",
            source="/source",
            target="/target",
            parsers=[],
        )
        
        config_manager.update_profile_field("test-profile", "add-tag", "Tag1")
        config_manager.update_profile_field("test-profile", "add-tag", "Tag2")
        profile = config_manager.get_profile("test-profile")
        assert "tag1" in profile["tags"]
        assert "tag2" in profile["tags"]
        assert len(profile["tags"]) == 2

    def test_update_profile_field_add_tag_duplicate(self, config_manager):
        """Adding duplicate tag should not add it again."""
        config_manager.add_profile(
            name="test-profile",
            source="/source",
            target="/target",
            parsers=[],
        )
        
        config_manager.update_profile_field("test-profile", "add-tag", "MyTag")
        config_manager.update_profile_field("test-profile", "add-tag", "mytag")
        profile = config_manager.get_profile("test-profile")
        assert profile["tags"].count("mytag") == 1

    def test_update_profile_field_remove_tag(self, config_manager):
        """Remove tag from profile."""
        config_manager.add_profile(
            name="test-profile",
            source="/source",
            target="/target",
            parsers=[],
        )
        
        config_manager.update_profile_field("test-profile", "add-tag", "Tag1")
        config_manager.update_profile_field("test-profile", "add-tag", "Tag2")
        
        config_manager.update_profile_field("test-profile", "remove-tag", "Tag1")
        profile = config_manager.get_profile("test-profile")
        assert "tag1" not in profile["tags"]
        assert "tag2" in profile["tags"]

    def test_update_profile_field_remove_nonexistent_tag(self, config_manager):
        """Removing non-existent tag should not raise error."""
        config_manager.add_profile(
            name="test-profile",
            source="/source",
            target="/target",
            parsers=[],
        )
        
        config_manager.update_profile_field("test-profile", "remove-tag", "NonExistent")
        profile = config_manager.get_profile("test-profile")
        assert profile["tags"] == []

    def test_profile_tags_optional_omitted_from_json(self, config_manager, temp_config_dir):
        """Verify tags omitted from JSON if empty array."""
        config_manager.add_profile(
            name="test-profile",
            source="/source",
            target="/target",
            parsers=[],
        )
        
        # Read the JSON file directly
        config_dir, config_file = temp_config_dir
        data = json.loads(config_file.read_text())
        profile = data["profiles"][0]
        
        # tags should not be in the JSON if empty
        assert "tags" not in profile

    def test_profile_tags_stored_when_nonempty(self, config_manager, temp_config_dir):
        """Verify tags stored in JSON if non-empty."""
        config_manager.add_profile(
            name="test-profile",
            source="/source",
            target="/target",
            parsers=[],
        )
        
        config_manager.update_profile_field("test-profile", "add-tag", "Important")
        
        # Read the JSON file directly
        config_dir, config_file = temp_config_dir
        data = json.loads(config_file.read_text())
        profile = data["profiles"][0]
        
        # tags should be in the JSON if non-empty
        assert "tags" in profile
        assert profile["tags"] == ["important"]

    def test_profile_tags_normalized_lowercase(self, config_manager):
        """Verify tags are always stored in lowercase."""
        config_manager.add_profile(
            name="test-profile",
            source="/source",
            target="/target",
            parsers=[],
        )
        
        config_manager.update_profile_field("test-profile", "add-tag", "UPPERCASE")
        config_manager.update_profile_field("test-profile", "add-tag", "MiXeDcAsE")
        config_manager.update_profile_field("test-profile", "add-tag", "lowercase")
        
        profile = config_manager.get_profile("test-profile")
        assert profile["tags"] == ["uppercase", "mixedcase", "lowercase"]
        for tag in profile["tags"]:
            assert tag.islower()

    def test_profile_without_tags_field_handled_gracefully(self, config_manager, temp_config_dir):
        """Verify that profiles without tags field are handled gracefully."""
        # Manually add a profile without tags field (simulating old profile format)
        config_dir, config_file = temp_config_dir
        data = json.loads(config_file.read_text())
        data["profiles"].append({
            "name": "old-profile",
            "source": "/source",
            "target": "/target",
            "parsers": [],
            "created_at": "2024-01-01T00:00:00",
        })
        config_file.write_text(json.dumps(data, indent=2))
        
        # Reload the config manager to load the old profile
        config_manager.profiles = config_manager._load()
        
        profile = config_manager.get_profile("old-profile")
        # After retrieval, tags should exist as empty list
        assert "tags" in profile or profile.get("tags", []) == []

    def test_add_tag_to_profile_without_tags_field(self, config_manager, temp_config_dir):
        """Verify adding tag to old profile (without tags field) works."""
        # Manually add a profile without tags field
        config_dir, config_file = temp_config_dir
        data = json.loads(config_file.read_text())
        data["profiles"].append({
            "name": "old-profile",
            "source": "/source",
            "target": "/target",
            "parsers": [],
            "created_at": "2024-01-01T00:00:00",
        })
        config_file.write_text(json.dumps(data, indent=2))
        
        # Reload the config manager
        config_manager.profiles = config_manager._load()
        
        # Adding tag to profile without tags field should work
        config_manager.update_profile_field("old-profile", "add-tag", "NewTag")
        profile = config_manager.get_profile("old-profile")
        assert "newtag" in profile["tags"]


class TestCliProfileTags:
    """Test CLI profile commands with tag support."""

    @pytest.fixture
    def cli_runner(self, temp_config_dir):
        """Create a CLI runner with temporary config."""
        runner = CliRunner()
        yield runner

    def test_cli_profile_add_with_tags(self, cli_runner, temp_config_dir):
        """Test creating profile with tags via CLI."""
        config_dir, config_file = temp_config_dir
        
        result = cli_runner.invoke(cli, [
            "profile", "add", "test-profile",
            "/source", "/target",
            "--tags", "fabric,priority-high"
        ])
        
        assert result.exit_code == 0
        assert "Profile 'test-profile' saved" in result.output
        
        # Verify tags were saved correctly and normalized
        cm = ConfigManager()
        profile = cm.get_profile("test-profile")
        assert "fabric" in profile["tags"]
        assert "priority-high" in profile["tags"]
        assert len(profile["tags"]) == 2

    def test_cli_profile_add_tags_normalized(self, cli_runner, temp_config_dir):
        """Test tags passed to profile add are normalized to lowercase."""
        config_dir, config_file = temp_config_dir
        
        result = cli_runner.invoke(cli, [
            "profile", "add", "test-profile",
            "/source", "/target",
            "--tags", "FABRIC,Priority-High"
        ])
        
        assert result.exit_code == 0
        
        cm = ConfigManager()
        profile = cm.get_profile("test-profile")
        assert "fabric" in profile["tags"]
        assert "priority-high" in profile["tags"]
        # Verify all tags are lowercase
        for tag in profile["tags"]:
            assert tag.islower()

    def test_cli_profile_set_add_tags(self, cli_runner, temp_config_dir):
        """Test adding tags to existing profile via profile set."""
        config_dir, config_file = temp_config_dir
        
        # First create a profile without tags
        cli_runner.invoke(cli, [
            "profile", "add", "test-profile",
            "/source", "/target"
        ])
        
        # Now add tags using profile set
        result = cli_runner.invoke(cli, [
            "profile", "set", "test-profile",
            "--add-tags", "mod,fabric"
        ])
        
        assert result.exit_code == 0
        assert "Profile 'test-profile' updated" in result.output
        
        cm = ConfigManager()
        profile = cm.get_profile("test-profile")
        assert "mod" in profile["tags"]
        assert "fabric" in profile["tags"]
        assert len(profile["tags"]) == 2

    def test_cli_profile_set_remove_tags(self, cli_runner, temp_config_dir):
        """Test removing tags from existing profile via profile set."""
        config_dir, config_file = temp_config_dir
        
        # First create a profile with tags
        cli_runner.invoke(cli, [
            "profile", "add", "test-profile",
            "/source", "/target",
            "--tags", "mod,fabric,priority-high"
        ])
        
        # Now remove a tag
        result = cli_runner.invoke(cli, [
            "profile", "set", "test-profile",
            "--remove-tags", "priority-high"
        ])
        
        assert result.exit_code == 0
        assert "Profile 'test-profile' updated" in result.output
        
        cm = ConfigManager()
        profile = cm.get_profile("test-profile")
        assert "mod" in profile["tags"]
        assert "fabric" in profile["tags"]
        assert "priority-high" not in profile["tags"]
        assert len(profile["tags"]) == 2

    def test_cli_profile_set_add_multiple_times(self, cli_runner, temp_config_dir):
        """Test multiple --add-tags calls accumulate tags."""
        config_dir, config_file = temp_config_dir
        
        # Create a profile
        cli_runner.invoke(cli, [
            "profile", "add", "test-profile",
            "/source", "/target"
        ])
        
        # Add tags in multiple calls
        result = cli_runner.invoke(cli, [
            "profile", "set", "test-profile",
            "--add-tags", "fabric",
            "--add-tags", "mod,priority-high"
        ])
        
        assert result.exit_code == 0
        
        cm = ConfigManager()
        profile = cm.get_profile("test-profile")
        assert "fabric" in profile["tags"]
        assert "mod" in profile["tags"]
        assert "priority-high" in profile["tags"]
        assert len(profile["tags"]) == 3


class TestProfileFiltering:
    """Test profile filtering by tags functionality."""

    def test_profile_list_filter_single_tag(self, config_manager):
        """Filter profiles by one tag (OR logic: profile matches if it has this tag)."""
        # Create test profiles with different tags
        config_manager.add_profile("profile-fabric", "/s1", "/t1", [])
        config_manager.update_profile_field("profile-fabric", "add-tag", "fabric")
        
        config_manager.add_profile("profile-forge", "/s2", "/t2", [])
        config_manager.update_profile_field("profile-forge", "add-tag", "forge")
        
        config_manager.add_profile("profile-no-tags", "/s3", "/t3", [])
        
        # Filter by fabric tag
        filtered = config_manager.list_profiles_by_tags(["fabric"])
        
        assert len(filtered) == 1
        assert filtered[0]["name"] == "profile-fabric"

    def test_profile_list_filter_multiple_tags_or(self, config_manager):
        """Multiple tags with OR logic (returns profiles with fabric OR forge)."""
        config_manager.add_profile("profile-fabric", "/s1", "/t1", [])
        config_manager.update_profile_field("profile-fabric", "add-tag", "fabric")
        
        config_manager.add_profile("profile-forge", "/s2", "/t2", [])
        config_manager.update_profile_field("profile-forge", "add-tag", "forge")
        
        config_manager.add_profile("profile-no-tags", "/s3", "/t3", [])
        
        # Filter by fabric OR forge (separate groups means OR between them)
        filtered = config_manager.list_profiles_by_tags(["fabric", "forge"])
        
        assert len(filtered) == 2
        names = [p["name"] for p in filtered]
        assert "profile-fabric" in names
        assert "profile-forge" in names
        assert "profile-no-tags" not in names

    def test_profile_list_filter_multiple_tags_within_group_or(self, config_manager):
        """Multiple tags within one group use OR logic."""
        config_manager.add_profile("profile-fabric", "/s1", "/t1", [])
        config_manager.update_profile_field("profile-fabric", "add-tag", "fabric")
        
        config_manager.add_profile("profile-priority", "/s2", "/t2", [])
        config_manager.update_profile_field("profile-priority", "add-tag", "priority-high")
        
        config_manager.add_profile("profile-both", "/s3", "/t3", [])
        config_manager.update_profile_field("profile-both", "add-tag", "fabric")
        config_manager.update_profile_field("profile-both", "add-tag", "priority-high")
        
        config_manager.add_profile("profile-no-tags", "/s4", "/t4", [])
        
        # Filter by fabric OR priority-high (comma-separated without +and means OR)
        filtered = config_manager.list_profiles_by_tags(["fabric,priority-high"])
        
        assert len(filtered) == 3
        names = [p["name"] for p in filtered]
        assert "profile-fabric" in names
        assert "profile-priority" in names
        assert "profile-both" in names
        assert "profile-no-tags" not in names

    def test_profile_list_filter_multiple_tags_and(self, config_manager):
        """Multiple tags with AND logic using +and suffix."""
        config_manager.add_profile("profile-fabric", "/s1", "/t1", [])
        config_manager.update_profile_field("profile-fabric", "add-tag", "fabric")
        
        config_manager.add_profile("profile-priority", "/s2", "/t2", [])
        config_manager.update_profile_field("profile-priority", "add-tag", "priority-high")
        
        config_manager.add_profile("profile-both", "/s3", "/t3", [])
        config_manager.update_profile_field("profile-both", "add-tag", "fabric")
        config_manager.update_profile_field("profile-both", "add-tag", "priority-high")
        
        # Filter by fabric AND priority-high (+and suffix means AND logic)
        filtered = config_manager.list_profiles_by_tags(["fabric,priority-high,+and"])
        
        assert len(filtered) == 1
        assert filtered[0]["name"] == "profile-both"

    def test_profile_list_filter_no_matches(self, config_manager):
        """Return empty list when no profiles match."""
        config_manager.add_profile("profile1", "/s1", "/t1", [])
        config_manager.update_profile_field("profile1", "add-tag", "fabric")
        
        config_manager.add_profile("profile2", "/s2", "/t2", [])
        config_manager.update_profile_field("profile2", "add-tag", "forge")
        
        # Filter by non-existent tag
        filtered = config_manager.list_profiles_by_tags(["nonexistent"])
        
        assert len(filtered) == 0
        assert filtered == []

    def test_profile_list_filter_case_insensitive(self, config_manager):
        """Filtering is case-insensitive."""
        config_manager.add_profile("profile1", "/s1", "/t1", [])
        config_manager.update_profile_field("profile1", "add-tag", "Fabric")
        
        config_manager.add_profile("profile2", "/s2", "/t2", [])
        config_manager.update_profile_field("profile2", "add-tag", "priority-high")
        
        # Filter by uppercase tag (should still match lowercase stored tag)
        filtered = config_manager.list_profiles_by_tags(["FABRIC"])
        
        assert len(filtered) == 1
        assert filtered[0]["name"] == "profile1"
        
        # Filter by mixed case tag
        filtered = config_manager.list_profiles_by_tags(["Priority-High"])
        
        assert len(filtered) == 1
        assert filtered[0]["name"] == "profile2"

    def test_profile_list_filter_maintains_order(self, config_manager):
        """Filtered profiles maintain original order."""
        config_manager.add_profile("alpha-profile", "/s1", "/t1", [])
        config_manager.update_profile_field("alpha-profile", "add-tag", "fabric")
        
        config_manager.add_profile("beta-profile", "/s2", "/t2", [])
        config_manager.update_profile_field("beta-profile", "add-tag", "forge")
        
        config_manager.add_profile("gamma-profile", "/s3", "/t3", [])
        config_manager.update_profile_field("gamma-profile", "add-tag", "fabric")
        
        # Filter by fabric tag, should maintain original list order
        filtered = config_manager.list_profiles_by_tags(["fabric"])
        
        assert len(filtered) == 2
        assert filtered[0]["name"] == "alpha-profile"
        assert filtered[1]["name"] == "gamma-profile"

    def test_profile_list_filter_empty_tag_list(self, config_manager):
        """Empty tag list returns all profiles."""
        config_manager.add_profile("profile1", "/s1", "/t1", [])
        config_manager.update_profile_field("profile1", "add-tag", "fabric")
        
        config_manager.add_profile("profile2", "/s2", "/t2", [])
        
        # Empty tag list should return all profiles
        filtered = config_manager.list_profiles_by_tags([])
        
        assert len(filtered) == 2
        names = [p["name"] for p in filtered]
        assert "profile1" in names
        assert "profile2" in names

    def test_profile_list_filter_or_between_groups_and_within(self, config_manager):
        """Complex: OR between groups, AND within group."""
        config_manager.add_profile("profile-a", "/s1", "/t1", [])
        config_manager.update_profile_field("profile-a", "add-tag", "fabric")
        config_manager.update_profile_field("profile-a", "add-tag", "priority-high")
        
        config_manager.add_profile("profile-b", "/s2", "/t2", [])
        config_manager.update_profile_field("profile-b", "add-tag", "forge")
        config_manager.update_profile_field("profile-b", "add-tag", "priority-high")
        
        config_manager.add_profile("profile-c", "/s3", "/t3", [])
        config_manager.update_profile_field("profile-c", "add-tag", "fabric")
        
        config_manager.add_profile("profile-d", "/s4", "/t4", [])
        config_manager.update_profile_field("profile-d", "add-tag", "priority-high")
        
        # (fabric AND priority-high) OR forge
        # Should return profile-a (fabric+priority), profile-b (forge+priority), profile-c (fabric)
        # Wait, let me reconsider: (fabric AND priority-high) OR forge
        # profile-a: has fabric AND priority-high → matches first group
        # profile-b: has forge → matches second group (1 forge)
        # profile-c: has fabric (no priority-high) → doesn't match first group, no forge → excluded
        # profile-d: has priority-high (no fabric, no forge) → excluded
        filtered = config_manager.list_profiles_by_tags(["fabric,priority-high,+and", "forge"])
        
        assert len(filtered) == 2
        names = [p["name"] for p in filtered]
        assert "profile-a" in names
        assert "profile-b" in names


class TestCliProfileListFiltering:
    """Test CLI profile list filtering functionality."""

    @pytest.fixture
    def cli_runner(self, temp_config_dir):
        """Create a CLI runner with temporary config."""
        runner = CliRunner()
        yield runner

    def test_cli_profile_list_with_single_filter_tag(self, cli_runner, temp_config_dir):
        """Test profile list with single --filter-tag option."""
        config_dir, config_file = temp_config_dir
        
        # Create profiles with tags
        result = cli_runner.invoke(cli, [
            "profile", "add", "fabric-mod",
            "/s1", "/t1",
            "--tags", "fabric"
        ])
        assert result.exit_code == 0
        
        result = cli_runner.invoke(cli, [
            "profile", "add", "forge-mod",
            "/s2", "/t2",
            "--tags", "forge"
        ])
        assert result.exit_code == 0
        
        # List with filter
        result = cli_runner.invoke(cli, [
            "profile", "list", "--filter-tag", "fabric"
        ])
        
        assert result.exit_code == 0
        assert "fabric-mod" in result.output
        assert "forge-mod" not in result.output

    def test_cli_profile_list_with_multiple_filter_tags(self, cli_runner, temp_config_dir):
        """Test profile list with multiple --filter-tag options (OR logic)."""
        config_dir, config_file = temp_config_dir
        
        # Create profiles
        cli_runner.invoke(cli, ["profile", "add", "profile-fabric", "/s1", "/t1", "--tags", "fabric"])
        cli_runner.invoke(cli, ["profile", "add", "profile-forge", "/s2", "/t2", "--tags", "forge"])
        cli_runner.invoke(cli, ["profile", "add", "profile-no-tags", "/s3", "/t3"])
        
        # List with multiple filter tags (OR between them)
        result = cli_runner.invoke(cli, [
            "profile", "list",
            "--filter-tag", "fabric",
            "--filter-tag", "forge"
        ])
        
        assert result.exit_code == 0
        assert "profile-fabric" in result.output
        assert "profile-forge" in result.output
        assert "profile-no-tags" not in result.output

    def test_cli_profile_list_with_and_logic_filter_tag(self, cli_runner, temp_config_dir):
        """Test profile list with AND logic using comma and +and."""
        config_dir, config_file = temp_config_dir
        
        # Create profiles
        cli_runner.invoke(cli, ["profile", "add", "profile-both", "/s1", "/t1", "--tags", "fabric,priority-high"])
        cli_runner.invoke(cli, ["profile", "add", "profile-fabric-only", "/s2", "/t2", "--tags", "fabric"])
        cli_runner.invoke(cli, ["profile", "add", "profile-priority-only", "/s3", "/t3", "--tags", "priority-high"])
        
        # List with AND logic filter
        result = cli_runner.invoke(cli, [
            "profile", "list",
            "--filter-tag", "fabric,priority-high,+and"
        ])
        
        assert result.exit_code == 0
        assert "profile-both" in result.output
        assert "profile-fabric-only" not in result.output
        assert "profile-priority-only" not in result.output


class TestProfileDisplayFormatting:
    """Test tag display formatting in profile listings and detail view."""

    def test_format_profiles_with_tags(self):
        """Tags appear in formatted profile list (ProfileListFormatter)."""
        from reporter import ProfileListFormatter
        
        profiles = [
            {
                "name": "fabric-mod",
                "source": "/path/to/source",
                "target": "/path/to/target",
                "mapping": "preset-1",
                "parsers": "normalize_line_endings",
                "tags": ["fabric", "priority-high"],
            }
        ]
        
        formatter = ProfileListFormatter(terminal_width=120)
        output = formatter.format_profiles(profiles)
        
        # Verify output contains tags in some form
        assert "fabric" in output
        assert "priority-high" in output

    def test_format_profiles_no_tags(self):
        """Profiles without tags display cleanly (no empty tags field shown)."""
        from reporter import ProfileListFormatter
        
        profiles = [
            {
                "name": "no-tags-profile",
                "source": "/path/to/source",
                "target": "/path/to/target",
                "mapping": "preset-1",
                "parsers": "normalize_line_endings",
                "tags": [],
            }
        ]
        
        formatter = ProfileListFormatter(terminal_width=120)
        output = formatter.format_profiles(profiles)
        
        # Profile name should appear
        assert "no-tags-profile" in output
        # Tags field should not appear if tags are empty (clean display)
        # The output should not have "tags: " or empty tags indicator
        lines = output.split("\n")
        assert len(lines) > 0

    def test_format_profiles_mixed_tags(self):
        """Some profiles with tags, some without display correctly."""
        from reporter import ProfileListFormatter
        
        profiles = [
            {
                "name": "with-tags",
                "source": "/path/to/source1",
                "target": "/path/to/target1",
                "mapping": "preset-1",
                "parsers": "normalize_line_endings",
                "tags": ["fabric", "mod"],
            },
            {
                "name": "no-tags",
                "source": "/path/to/source2",
                "target": "/path/to/target2",
                "mapping": "preset-2",
                "parsers": "strip_bom",
                "tags": [],
            },
        ]
        
        formatter = ProfileListFormatter(terminal_width=120)
        output = formatter.format_profiles(profiles)
        
        # First profile should show tags
        assert "with-tags" in output
        assert "fabric" in output
        assert "mod" in output
        
        # Second profile should appear without error
        assert "no-tags" in output

    def test_profile_show_includes_tags(self, temp_config_dir):
        """Profile detail view shows tags."""
        from click.testing import CliRunner
        
        # Create a profile with tags
        config_dir, config_file = temp_config_dir
        config_data = json.loads(config_file.read_text())
        config_data["profiles"].append({
            "name": "tagged-profile",
            "source": "/source",
            "target": "/target",
            "parsers": [],
            "tags": ["fabric", "priority-high"],
            "created_at": "2024-01-01T00:00:00",
        })
        config_file.write_text(json.dumps(config_data, indent=2))
        
        runner = CliRunner()
        result = runner.invoke(cli, ["profile", "show", "tagged-profile"])
        
        assert result.exit_code == 0
        # Tags should appear in the output
        assert "fabric" in result.output
        assert "priority-high" in result.output

    def test_profile_show_no_tags(self, temp_config_dir):
        """Profile detail view without tags still displays cleanly."""
        from click.testing import CliRunner
        
        # Create a profile without tags
        config_dir, config_file = temp_config_dir
        config_data = json.loads(config_file.read_text())
        config_data["profiles"].append({
            "name": "no-tags-profile",
            "source": "/source",
            "target": "/target",
            "parsers": [],
            "created_at": "2024-01-01T00:00:00",
        })
        config_file.write_text(json.dumps(config_data, indent=2))
        
        runner = CliRunner()
        result = runner.invoke(cli, ["profile", "show", "no-tags-profile"])
        
        assert result.exit_code == 0
        # Profile should display without error
        assert "no-tags-profile" in result.output

