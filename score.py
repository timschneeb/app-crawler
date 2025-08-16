import datetime

import langdetect
from github import UnknownObjectException
from github.Repository import Repository


def calc_github_score(repo: Repository, trace: bool = False) -> float:
    """
    Calculate the score for a GitHub app based on its popularity and activity.
    """
    
    trace_log = repo.full_name + "\n"
    try:
        desc = repo.description or ""
        stars = repo.stargazers_count
        
        weights = {
            "active": 30,
            "description": 10,
            "readme": 20,
            "release_download": 40,
            "english_desc": 25,
            "stars": 30  # stars will be scaled
        }

        # Score accumulators
        score = 0
        max_score = sum(weights.values())
    
        def get_and_trace(key: str):
            nonlocal trace_log
            trace_log += "\t+{} for {}\n".format(weights[key], key)
            return weights[key]
    
        # Description
        if len(desc) > 0:
            score += get_and_trace("description")

            # English description
            langdetect.DetectorFactory.seed = 0
            if langdetect.detect(desc) == 'en':
                score += get_and_trace("english_desc")
                
        try: 
            # At least 600 bytes
            if repo.get_readme().size > 600:
                score += get_and_trace("readme")
        except UnknownObjectException:
            # If the repo does not have a README, we skip this part
            pass
    
        # Release download links
        if repo.has_downloads:
            score += get_and_trace("release_download")
    
        # Check if the repo has been updated in the last 180 days
        if (datetime.datetime.now(datetime.UTC) - repo.updated_at).days <= 180:
            score += get_and_trace("active")
    
        # Stars (scale to avoid huge star counts dominating)
        star_score = min(float(weights["stars"]), weights["stars"] * (stars / 500.0))  # full score at 500 stars
        score += star_score
            
        if star_score > 0:
            # Log if stars contributed to the score
            get_and_trace("stars")
    
        # Normalize to 0-100
        final_score =  round((score / max_score) * 100, 2)
        trace_log += f"\t= {final_score}\n"

        with (open("score.log", 'a') as f):
            f.write(trace_log)
            f.write("\n")
        return final_score
        
    except Exception as e:
        print(f"Error calculating score for {repo.url}: {e}")
        return 0.0