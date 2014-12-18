"""
Provides a UserPartition driver for cohorts.
"""
import logging

from courseware import courses
from courseware.masquerade import get_masquerading_group_info
from xmodule.partitions.partitions import NoSuchUserPartitionGroupError

from .cohorts import get_cohort, get_group_info_for_cohort


log = logging.getLogger(__name__)


class CohortPartitionScheme(object):
    """
    This scheme uses lms cohorts (CourseUserGroups) and cohort-partition
    mappings (CourseUserGroupPartitionGroup) to map lms users into Partition
    Groups.
    """

    # pylint: disable=unused-argument
    @classmethod
    def get_group_for_user(cls, course_key, user, user_partition, track_function=None):
        """
        Returns the Group from the specified user partition to which the user
        is assigned, via their cohort membership and any mappings from cohorts
        to partitions / groups that might exist.

        If the user has not yet been assigned to a cohort, an assignment *might*
        be created on-the-fly, as determined by the course's cohort config.
        Any such side-effects will be triggered inside the call to
        cohorts.get_cohort().

        If the user has no cohort mapping, or there is no (valid) cohort ->
        partition group mapping found, the function returns None.
        """
        # If the current user is masquerading as being in a group belonging to the
        # specified user partition then return the masquerading group.
        group_id, user_partition_id = get_masquerading_group_info(user, course_key)
        if group_id is not None and user_partition_id == user_partition.id:
            try:
                return user_partition.get_group(group_id)
            except NoSuchUserPartitionGroupError:
                # If the group no longer exists then the masquerade is not in effect
                pass

        cohort = get_cohort(user, course_key)
        if cohort is None:
            # student doesn't have a cohort
            return None

        group_id, partition_id = get_group_info_for_cohort(cohort)
        if partition_id is None:
            # cohort isn't mapped to any partition group.
            return None

        if partition_id != user_partition.id:
            # if we have a match but the partition doesn't match the requested
            # one it means the mapping is invalid.  the previous state of the
            # partition configuration may have been modified.
            log.warn(
                "partition mismatch in CohortPartitionScheme: %r",
                {
                    "requested_partition_id": user_partition.id,
                    "found_partition_id": partition_id,
                    "found_group_id": group_id,
                    "cohort_id": cohort.id,
                }
            )
            # fail silently
            return None

        try:
            return user_partition.get_group(group_id)
        except NoSuchUserPartitionGroupError:
            # if we have a match but the group doesn't exist in the partition,
            # it means the mapping is invalid.  the previous state of the
            # partition configuration may have been modified.
            log.warn(
                "group not found in CohortPartitionScheme: %r",
                {
                    "requested_partition_id": user_partition.id,
                    "requested_group_id": group_id,
                    "cohort_id": cohort.id,
                },
                exc_info=True
            )
            # fail silently
            return None


def get_cohorted_user_partition(course_key):
    """
    Returns the first user partition from the specified course which uses the CohortPartitionScheme,
    or None if one is not found. Note that it is currently recommended that each course have only
    one cohorted user partition.
    """
    course = courses.get_course_by_id(course_key)
    for user_partition in course.user_partitions:
        if user_partition.scheme == CohortPartitionScheme:
            return user_partition

    return None
