# Import libraries
import sys

from config import registry as reg
from config import col_ids as col

import pandas as pd
import numpy as np

import json
from tabulate import tabulate

from data_input import file_loader as load

from benchmark import by_methods as by_mtd

# Import mapping tables
ref_country = pd.read_csv(reg.project_path.joinpath('ref_tables', 'country_table.csv'))


def collect_parent_ids():
    """
    """

    parent_ids = parent_conso = pd.DataFrame()

    print('Read parent company ids from initial collection tables')

    for company_type in reg.company_types:
        print('... ' + str(company_type))

        df = load.company_ids_from_orbis_xls(
            reg.case_path.joinpath(r'input/parent_ids'),
            reg.parent_id_files_n[company_type],
            company_type,
            'parent'
        )

        parent_ids = parent_ids.append(df)

    parent_ids = parent_ids[['guo_bvd9', 'parent_bvd9']]

    print('Initial count')

    print(parent_ids.head())

    print(parent_ids.describe())

    # Parents without any identified corporate GUO50 or GUO25 are considered as Highest Corporate Owner
    parent_ids['guo_bvd9'] = np.where(parent_ids['guo_bvd9'].isna(), parent_ids['parent_bvd9'], parent_ids['guo_bvd9'])

    print('Completed count')

    print(parent_ids.head())

    print(parent_ids.describe())

    parent_ids.drop_duplicates(keep='first', inplace=True)

    return parent_ids


def load_parent_ids(type, level):
    """
    Load identification data for parent and guo companies
    """

    parent_ids = parent_conso = pd.DataFrame()

    report = {}

    print('Read parent company ids from input tables')

    parent_ids = load.company_ids_from_orbis_xls(
        reg.case_path.joinpath(r'input/parent_ids'),
        reg.parent_id_files_n[type],
        type,
        level
    )

    # Merge with ref_country for allocation to world player categories
    parent_ids = pd.merge(
        parent_ids,
        ref_country[['country_2DID_iso', 'country_3DID_iso', 'world_player']],
        left_on='country_2DID_iso', right_on='country_2DID_iso',
        how='left',
        suffixes=(False, False)
    )

    parent_ids.drop_duplicates(keep='first', inplace=True)

    return parent_ids


def load_parent_fins():
    """
    Load financials data for parent companies
    """
    parent_fins = pd.DataFrame()

    print('Read parent companies financials input files')

    parent_fins = load.parent_fins_from_orbis_xls(
        reg.case_path.joinpath(r'input/parent_fins'),
        reg.parent_fin_files_n,
        reg.oprev_ys,
        reg.rnd_ys,
        reg.LY
    )

    print('bvd9:' + str(pd.Series(parent_fins.bvd9.unique()).count()))

    parent_fins.dropna(subset=reg.rnd_ys + reg.oprev_ys, how='all', inplace=True)
    parent_fins.drop_duplicates(subset=['bvd9', 'parent_conso'], keep='first', inplace=True)

    print('bvd9_with_fins:' + str(pd.Series(parent_fins.bvd9.unique()).count()))

    for cols in reg.rnd_ys:
        parent_fins[parent_fins[cols] < 0] = 0

    parent_fins['rnd_sum'] = parent_fins[reg.rnd_ys].sum(axis=1, skipna=True)
    parent_fins['oprev_sum'] = parent_fins[reg.oprev_ys].sum(axis=1, skipna=True)

    # parent_fins['Emp_number_y' + reg.LY] = parent_fins['Emp_number_y' + reg.LY].astype(int)

    # melted = parent_fins.melt(
    #     id_vars=['bvd9'],
    #     value_vars=['Emp_number_y' + reg.LY, 'operating_revenue_y' + reg.LY, 'sales_y' + reg.LY] + reg.rnd_ys[::-1],
    #     var_name='merge_label', value_name='value')
    #
    # melted['type'] = [str(s[:-4]) for s in melted['merge_label']]
    # melted['year'] = [int('20' + s[-2:]) for s in melted['merge_label']]
    #
    # melted.to_csv(reg.parent['fin_melted'],
    #               columns=['bvd9', 'year', 'type', 'value'],
    #               float_format='%.10f',
    #               index=False,
    #               na_rep='#N/A'
    #               )

    parent_fins.dropna(subset=['bvd9'], inplace=True)
    parent_fins.drop_duplicates(keep='first', inplace=True)

    return parent_fins[col.parent_fins]


def select_parent_ids_with_rnd(
        parent_fins
):
    # Identify the top companies that constitute 99% of the R&D expenses
    start = 0.0
    count = 0

    print('Select parent companies representing ' + str(reg.rnd_limit) + ' of total RnD')

    parent_fins.sort_values(by='rnd_mean', ascending=False, na_position='last')

    while start < reg.rnd_limit * parent_fins['rnd_mean'].sum():
        count += 1
        start = parent_fins.nlargest(count, ['rnd_mean'])['rnd_mean'].sum()

    selected_parent_ids = parent_fins.nlargest(count, ['rnd_mean'])

    selected_parent_ids.drop_duplicates(subset=['bvd9'], keep='first')

    selected_parent_ids.drop_duplicates(keep='first', inplace=True)

    return selected_parent_ids


def collect_sub_ids():
    """
    Consolidate a unique list of subsidiaries
    """
    # Initialize DF
    sub_ids = pd.DataFrame()
    report = {}

    print('Read subsidiary identification input tables')

    sub_ids = load.sub_collect_from_orbis_xls(
        reg.case_path.joinpath(r'input/sub_collect'),
        reg.sub_collect_files_n
    )

    return sub_ids[['bvd9', 'sub_bvd9']]


def load_sub_ids():
    """
    Consolidate a unique list of subsidiaries
    """
    # Initialize DF
    sub_ids = pd.DataFrame()
    report = {}

    print('Read subsidiary identification input tables')

    sub_ids = load.company_ids_from_orbis_xls(
        reg.case_path.joinpath(r'input/sub_ids'),
        reg.sub_id_files_n,
        'consolidated',
        'sub'
    )

    print('Merge with ref_country ...')

    # Merge with ref_country for allocation to world player categories
    sub_ids = pd.merge(
        sub_ids[['sub_company_name', 'sub_bvd9', 'sub_conso', 'sub_bvd_id', 'sub_legal_entity_id',
                 'sub_country_2DID_iso', 'sub_NACE_4Dcode', 'sub_NACE_desc']],
        ref_country[['country_2DID_iso', 'country_3DID_iso', 'world_player']],
        left_on='sub_country_2DID_iso', right_on='country_2DID_iso',
        how='left',
        suffixes=(False, False)
    ).rename(columns={'country_3DID_iso': 'sub_country_3DID_iso', 'world_player': 'sub_world_player'})

    sub_ids.dropna(subset=['sub_bvd9'], inplace=True)
    sub_ids.drop_duplicates(subset=['sub_bvd9'], keep='first', inplace=True)

    return sub_ids
    # return report, sub_ids


def load_sub_fins():
    """
    Loads financials for subsidiaries
    """
    sub_fins = pd.DataFrame()
    report = {}

    print('Read subsidiaries financials input tables')

    sub_fins = load.sub_fins_from_orbis_xls(
        reg.case_path.joinpath(r'input/sub_fins'),
        reg.sub_fin_files_n,
        reg.oprev_ys,
        reg.rnd_ys
    )

    # sub_fins = sub_fins[sub_fins['sub_bvd9'].isin(select_subs['sub_bvd9'])]

    sub_fins.dropna(subset=reg.rnd_ys + reg.oprev_ys, how='all', inplace=True)
    sub_fins.drop_duplicates(subset=['sub_bvd9', 'sub_conso'], keep='first', inplace=True)

    for cols in reg.rnd_ys:
        sub_fins[sub_fins[cols] < 0] = 0

    sub_fins['rnd_sum'] = sub_fins[reg.rnd_ys].sum(axis=1, skipna=True)
    sub_fins['oprev_sum'] = sub_fins[reg.oprev_ys].sum(axis=1, skipna=True)

    # sub_fins_w_fin = sub_fins.dropna(subset=reg.oprev_ys, how='all')

    # report['Returned by ORBIS'] = {'sub_bvd9_in_selected_bvd9': sub_fins['sub_bvd9'].count().sum(),
    #                                'unique_sub_bvd9': sub_fins['sub_bvd9'].nunique(),
    #                                'unique_has_fin': sub_fins_w_fin['sub_bvd9'].nunique(),
    #                                }

    # # Merging subsidiary ref_country for allocation to world player categories and countries
    # merged = pd.merge(
    #     sub_fins_w_fin, ref_country[['country_2DID_iso', 'country_3DID_iso', 'region', 'world_player']],
    #     left_on='country_iso', right_on='country_2DID_iso',
    #     how='left',
    #     suffixes=(False, False)
    # )

    # melted = sub_fins.melt(
    #     id_vars=['sub_company_name', 'sub_bvd9', 'trade_desc', 'products&services_desc', 'full_overview_desc'],
    #     value_vars=reg.oprev_ys[::-1] + reg.rnd_ys[::-1],
    #     var_name='merge_label', value_name='value')
    #
    # melted['type'] = [str(s[:-4]) for s in melted['merge_label']]
    # melted['year'] = [int('20' + s[-2:]) for s in melted['merge_label']]
    #
    # melted.to_csv(reg.sub['fin_melted'],
    #               columns=['sub_company_name', 'sub_bvd9', 'year', 'type', 'value'],
    # float_format = '%.10f',
    # index = False,
    # na_rep = '#N/A'
    # )

    sub_fins.drop_duplicates(keep='first', inplace=True)

    return sub_fins
    # return report, sub_fins


def screen_sub_ids_for_method(
        parent_ids,
        sub_ids
):
    """
    Add bolean masks for the implementation of different rnd calculation method
    keep_all: Keep all parent companies and all subsidiaries
    keep_comps: Keep all parent companies and exclude subsidiaries that are parent companies from subsidiaries list
    keep_subs: Exclude parent companies that are a subsidiary from companies list and keep all subsidiaries

    """
    report = {}

    print('Screen subsidiaries for method flags')

    # Flag parent companies that are a subsidiary of another parent company and vice versa
    # sub_ids['is_comp_a_sub'] = sub_ids['is_comp_a_sub'].isin(sub_ids['sub_bvd9'])
    # sub_ids['is_sub_a_comp'] = sub_ids['sub_bvd9'].isin(sub_ids['bvd9'])
    # sub_ids['has_fin'] = sub_ids['sub_bvd9'].isin(sub_fins['sub_bvd9'])

    # Flag subsidiaries that are subsidiaries of multiple parent companies
    sub_ids['is_sub_a_duplicate'] = sub_ids['sub_bvd9'].duplicated(keep=False)

    sub_ids['keep_all'] = True

    # sub_ids.loc[~sub_ids['bvd9'].isin(sub_ids['sub_bvd9']), 'keep_subs'] = True
    # sub_ids.loc[sub_ids['keep_subs'] != True, 'keep_subs'] = False
    # sub_ids.loc[~sub_ids['sub_bvd9'].isin(parent_ids['bvd9']), 'keep_comps'] = True
    # sub_ids.loc[sub_ids['keep_comps'] != True, 'keep_comps'] = False

    sub_ids['keep_subs'] = ~sub_ids['bvd9'].isin(sub_ids['sub_bvd9'])
    sub_ids['keep_comps'] = ~sub_ids['sub_bvd9'].isin(parent_ids['bvd9'])

    # for method in reg.methods:
    #     print('Flag strategy: ' + str(method))
    #
    #     report['From ORBIS with applied method: ' + str(method)] = {
    #         'selected_bvd9': sub_ids['bvd9'][sub_ids[method] == True].nunique(),
    #         'unique_sub_bvd9': sub_ids['sub_bvd9'][sub_ids[method] == True].nunique()
    #         # 'unique_has_fin': sub_ids['sub_bvd9'][
    #         #     (sub_ids[method] == True) & (sub_ids['has_fin'] == True)].nunique()
    #     }

    sub_ids.drop_duplicates(keep='first', inplace=True)

    return sub_ids
    # return report, sub_ids


def screen_sub_fins_for_keywords(
        sub_fins
):
    print('Screen subsidiary activity for keywords')

    report = {}

    for category in reg.categories:

        sub_fins[category] = False

        for keyword in reg.keywords[category]:
            sub_fins[category] |= sub_fins['trade_desc'].str.contains(keyword, case=False, regex=False) | \
                                  sub_fins['products&services_desc'].str.contains(keyword, case=False, regex=False) | \
                                  sub_fins['full_overview_desc'].str.contains(keyword, case=False, regex=False)

    # screen_subs = sub_fins.loc[:, ['sub_company_name', 'sub_bvd9', 'sub_bvd_id'] + reg.categories]

    sub_fins['sub_turnover_sum'] = sub_fins.loc[:, reg.oprev_ys_for_exp].sum(axis=1)

    sub_fins['keyword_mask'] = list(
        map(bool, sub_fins[[cat for cat in reg.categories if cat not in ['generation', 'rnd']]].sum(axis=1)))

    sub_fins['sub_turnover_sum_masked'] = sub_fins['sub_turnover_sum'].mask(~sub_fins['keyword_mask'])

    # report['Returned by ORBIS'] = {
    #     'unique_is_matching_a_keyword': sub_fins['sub_bvd9'][sub_fins['keyword_mask'] == True].nunique()
    # }

    sub_fins.drop_duplicates(keep='first', inplace=True)

    return sub_fins
    # return report, sub_fins


def compute_exposure(
        parent_ids,
        parent_fins,
        selected_sub_ids,
        sub_fins
):
    sub_exposure_conso = pd.DataFrame()
    parent_exposure_conso = pd.DataFrame()
    # report_keyword_match = {}
    # report_exposure = {'at_subsidiary_level': {}, 'at_parent_level': {}}

    print('Compute exposure for strategy:')

    for method in reg.methods:
        print('... ' + str(method))
        sub_exposure = pd.DataFrame()

        # Merging selected subsidiaries by method with masked turnover and turnover
        sub_exposure = pd.merge(
            selected_sub_ids[selected_sub_ids[method] == True], sub_fins,
            left_on=['sub_bvd9'], right_on=['sub_bvd9'],
            how='left'
        )

        sub_exposure['keyword_mask'] = np.where(sub_exposure['keyword_mask'] == True, 1, 0)

        # Calculating group exposure
        parent_exposure = sub_exposure[
            ['bvd9', 'keyword_mask', 'sub_turnover_sum_masked', 'sub_turnover_sum']
        ].groupby(['bvd9']).sum().rename(
            columns={'keyword_mask': 'keyword_mask_sum_in_parent',
                     'sub_turnover_sum': 'total_sub_turnover_sum_in_parent',
                     'sub_turnover_sum_masked': 'total_sub_turnover_sum_masked_in_parent'}
        )

        parent_exposure['parent_exposure'] = parent_exposure['total_sub_turnover_sum_masked_in_parent'] / \
                                             parent_exposure['total_sub_turnover_sum_in_parent']

        parent_exposure['method'] = str(method)

        parent_exposure.reset_index(inplace=True)

        parent_exposure_conso = parent_exposure_conso.append(parent_exposure)

        # parent_exposure_conso.dropna(subset=['parent_exposure'], inplace=True)

        # Calculating subsidiary level exposure
        sub_exposure = pd.merge(
            sub_exposure, parent_exposure[
                ['bvd9', 'keyword_mask_sum_in_parent', 'total_sub_turnover_sum_masked_in_parent',
                 'total_sub_turnover_sum_in_parent', 'parent_exposure']],
            left_on='bvd9', right_on='bvd9',
            how='left'
        )

        sub_exposure['sub_exposure'] = sub_exposure['sub_turnover_sum_masked'] / sub_exposure[
            'total_sub_turnover_sum_in_parent']

        sub_exposure['method'] = str(method)

        # report_keyword_match['From ORBIS with applied method: ' + str(method)] = {
        #     'sub_bvd9_in_selected_bvd9': selected_sub_ids['sub_bvd9'][selected_sub_ids[method] == True].count().sum(),
        #     'unique_is_matching_a_keyword': sub_exposure['sub_bvd9'][sub_exposure['keyword_mask'] == True].nunique()
        # }
        #
        # report_exposure['at_parent_level'].update({
        #     'With method: ' + str(method): {
        #         'Total_exposure': parent_exposure['parent_exposure'].sum()
        #     }
        # })
        #
        # report_exposure['at_subsidiary_level'].update({
        #     'With method: ' + str(method): {
        #         'Total_exposure': sub_exposure['sub_exposure'].sum()
        #     }
        # })

        sub_exposure_conso = sub_exposure_conso.append(sub_exposure)

    # sub_exposure_conso.dropna(subset=['sub_exposure'], inplace=True)

    parent_exposure_conso = pd.merge(
        parent_exposure_conso, parent_ids[['bvd9', 'company_name']],
        left_on='bvd9', right_on='bvd9',
        how='left'
    ).rename(columns={'company_name': 'parent_name'})

    parent_exposure_conso = pd.merge(
        parent_exposure_conso, parent_fins[['bvd9', 'parent_conso']],
        left_on='bvd9', right_on='bvd9',
        how='left'
    )

    sub_exposure_conso = pd.merge(
        sub_exposure_conso, parent_ids[['bvd9', 'company_name']],
        left_on='bvd9', right_on='bvd9',
        how='left'
    ).rename(columns={'company_name': 'parent_name'})

    sub_exposure_conso = pd.merge(
        sub_exposure_conso, parent_fins[['bvd9', 'parent_conso']],
        left_on='bvd9', right_on='bvd9',
        how='left'
    )

    parent_exposure_conso.drop_duplicates(keep='first', inplace=True)
    sub_exposure_conso.drop_duplicates(keep='first', inplace=True)

    return parent_exposure_conso, sub_exposure_conso
    # return report_keyword_match, report_exposure, parent_exposure_conso, sub_exposure_conso


def compute_parent_rnd(
        parent_exposure,
        parent_fins
):
    print('Compute parent level rnd')

    parent_rnd_conso = pd.DataFrame()

    report_parent_rnd = {}

    parent_rnd = pd.merge(parent_exposure[
                              ['bvd9', 'parent_name', 'total_sub_turnover_sum_masked_in_parent',
                               'total_sub_turnover_sum_in_parent', 'parent_exposure', 'method']
                          ], parent_fins,
                          left_on='bvd9', right_on='bvd9',
                          how='left'
                          )

    for method in reg.methods:
        parent_rnd_method = parent_rnd[parent_rnd['method'] == method]

        # Calculating group level rnd
        rnd_melt = parent_rnd_method.melt(
            id_vars=['bvd9', 'parent_name', 'parent_conso', 'total_sub_turnover_sum_masked_in_parent',
                     'total_sub_turnover_sum_in_parent', 'parent_exposure'],
            value_vars=reg.rnd_ys,
            var_name='rnd_label', value_name='parent_rnd')

        rnd_melt['year'] = [int('20' + s[-2:]) for s in rnd_melt['rnd_label']]

        oprev_melt = parent_rnd_method.melt(
            id_vars=['bvd9'],
            value_vars=reg.oprev_ys,
            var_name='oprev_label', value_name='parent_oprev')

        oprev_melt['year'] = [int('20' + s[-2:]) for s in oprev_melt['oprev_label']]

        parent_rnd_method_melted = pd.merge(
            rnd_melt,
            oprev_melt,
            left_on=['bvd9', 'year'],
            right_on=['bvd9', 'year'],
            how='left')

        parent_rnd_method_melted['parent_rnd_clean'] = parent_rnd_method_melted['parent_rnd'] * \
                                                       parent_rnd_method_melted[
                                                           'parent_exposure']

        parent_rnd_method_melted['method'] = str(method)

        # parent_rnd_method_melted.dropna(subset=['parent_exposure', 'parent_rnd', 'parent_rnd_clean'], how='all',
        #                                 inplace=True)

        parent_rnd_conso = parent_rnd_conso.append(parent_rnd_method_melted)

        # report_parent_rnd.update(
        #     pd.DataFrame.to_dict(
        #         parent_rnd_method_melted[['year', 'parent_rnd_clean']].groupby(
        #             ['year']).sum().rename(columns={'parent_rnd_clean': 'with_method: ' + str(method)})
        #     )
        # )

    parent_rnd_conso.drop_duplicates(keep='first', inplace=True)

    return parent_rnd_conso
    # return report_parent_rnd, parent_rnd_conso


def compute_guo_rnd(
        parent_rnd,
        parent_ids,
        guo_ids
):
    print('Compute guo level rnd')

    guo_rnd_conso = pd.DataFrame()

    # Merging with guo_ids

    # print('parent_rnd_clean = ' + str(parent_rnd.parent_rnd_clean.sum()))
    # print('parent_rnd = ' + str(parent_rnd.parent_rnd.sum()))
    # print('parent_oprev = ' + str(parent_rnd.parent_oprev.sum()))
    # print('parent_exposure = ' + str(parent_rnd.parent_exposure.sum()))

    parent_ids = parent_ids[['bvd9', 'company_name', 'guo_bvd9']].drop_duplicates(subset=['bvd9', 'guo_bvd9'])

    parent_rnd = pd.merge(
        parent_rnd,
        parent_ids,
        left_on='bvd9', right_on='bvd9',
        how='left',
        suffixes=(False, False)
    )

    for method in reg.methods:
        parent_rnd_method = parent_rnd[parent_rnd['method'] == method]

        # guo_rnd_method_ungrouped = guo_rnd_method[guo_rnd_method['guo_bvd9'].isna()].copy()
        #
        # guo_rnd_method_ungrouped['guo_bvd9'] = guo_rnd_method_ungrouped['bvd9']
        #
        # guo_rnd_method_ungrouped['guo_name'] = guo_rnd_method_ungrouped['company_name']
        #
        # guo_rnd_method_ungrouped['is_guo'] = False
        #
        # guo_rnd_method_ungrouped.rename(columns={
        #     'parent_oprev': 'guo_oprev',
        #     'parent_rnd': 'guo_rnd',
        #     'parent_exposure': 'guo_exposure',
        #     'parent_rnd_clean': 'guo_rnd_clean'
        # }, inplace=True)

        guo_rnd_method = parent_rnd_method.groupby(['guo_bvd9', 'year']).agg(
            {'parent_oprev': 'sum', 'parent_rnd': 'sum', 'parent_rnd_clean': 'sum', 'parent_exposure': 'mean'}
        )

        guo_rnd_method.reset_index(inplace=True)

        guo_rnd_method.rename(columns={
            'parent_oprev': 'guo_oprev_from_parent',
            'parent_rnd': 'guo_rnd_from_parent',
            'parent_exposure': 'guo_exposure_from_parent',
            'parent_rnd_clean': 'guo_rnd_clean_from_parent'
        }, inplace=True)

        guo_rnd_method['guo_exposure'] = guo_rnd_method['guo_rnd_clean_from_parent'] / guo_rnd_method[
            'guo_rnd_from_parent']

        guo_rnd_method['method'] = str(method)

        guo_rnd_conso = guo_rnd_conso.append(guo_rnd_method)

    guo_rnd_conso = pd.merge(
        guo_rnd_conso,
        guo_ids,
        left_on='guo_bvd9', right_on='guo_bvd9',
        how='left',
        suffixes=(False, False)
    )

    # print('parent_rnd_clean = ' + str(guo_rnd_conso.guo_rnd_clean.sum()))
    # print('parent_rnd = ' + str(guo_rnd_conso.guo_rnd.sum()))
    # print('parent_oprev = ' + str(guo_rnd_conso.guo_oprev.sum()))
    # print('parent_exposure = ' + str(guo_rnd_conso.guo_exposure.sum()))

    guo_rnd_conso.drop_duplicates(keep='first', inplace=True)

    return guo_rnd_conso
    # return report_parent_rnd, parent_rnd_conso


def compute_sub_rnd(
        sub_exposure,
        parent_rnd
):
    print('Compute subsidiary level rnd')

    sub_rnd_conso = pd.DataFrame()

    report_sub_rnd = {}

    for method in reg.methods:
        sub_rnd = pd.DataFrame()

        sub_exposure_method = sub_exposure[sub_exposure['method'] == method]
        parent_rnd_method = parent_rnd[parent_rnd['method'] == method]

        # Calculating subsidiary level rnd
        sub_rnd = pd.merge(
            sub_exposure_method, parent_rnd_method[['bvd9', 'parent_rnd', 'year', 'parent_rnd_clean']],
            left_on='bvd9', right_on='bvd9',
            how='left',
            suffixes=(False, False)
        )

        # df = sub_rnd[
        #     ['bvd9', 'year', 'sub_exposure']
        # ].groupby(['bvd9', 'year']).sum().rename(
        #     columns={'sub_exposure': 'parent_exposure_from_sub'}
        # )
        #
        # sub_rnd = pd.merge(
        #     sub_rnd, df,
        #     left_on=['bvd9', 'year'], right_on=['bvd9', 'year'],
        #     how='left',
        #     suffixes=(False, False)
        # )

        # sub_rnd['sub_rnd_clean'] = sub_rnd['parent_rnd_clean'] * sub_rnd['sub_exposure'] / sub_rnd[
        #     'parent_exposure_from_sub']

        sub_rnd['sub_rnd_clean'] = sub_rnd['parent_rnd_clean'] * sub_rnd['sub_exposure'] / sub_rnd[
            'parent_exposure']

        sub_rnd['method'] = str(method)

        sub_rnd_conso = sub_rnd_conso.append(sub_rnd)

        # report_sub_rnd.update(
        #     pd.DataFrame.to_dict(
        #         sub_rnd[['year', 'sub_rnd_clean']].groupby(['year']).sum().rename(
        #             columns={'sub_rnd_clean': 'with_method: ' + str(method)})
        #     )
        # )



    # melted = sub_rnd_conso.melt(
    #     id_vars=['sub_bvd9'],
    #     value_vars=reg.rnd_ys[::-1],
    #     var_name='merge_label', value_name='sub_rnd')
    #
    # melted['year'] = [int('20' + s[-2:]) for s in melted['merge_label']]
    #
    # melted.to_csv(reg.sub['melted'],
    #               columns=['sub_company_name', 'sub_bvd9', 'year', 'type', 'value'],
    # float_format = '%.10f',
    # index = False,
    # na_rep = '#N/A'
    # )

    sub_rnd_conso.drop_duplicates(keep='first', inplace=True)

    return sub_rnd_conso
    # return report_sub_rnd, sub_rnd_conso[sub_rnd_conso_cols]


def update_report(
        report
):
    """
    Update a json file with reporting outputs and pretty print a readable statistics report
    :param report: dictionary of reporting outputs
    :param reg: dictionary of configuration parameters for the considered use case
    :return: Nothing
    """

    def convert(o):
        if isinstance(o, np.int32): return int(o)

    print('Update report.json file ...')

    with open(reg.case_path.joinpath(r'report.json'), 'w') as file:
        json.dump(report, file, indent=4, default=convert)


def pprint_report(
        report
):
    """
    Pretty print a readable statistics report
    :param report: dictionary of reporting outputs
    :param reg: dictionary of configuration parameters for the considered use case
    :return: Nothing
    """

    def convert(o):
        if isinstance(o, np.int32): return int(o)

    with open(reg.case_path.joinpath(r'report.txt'), 'w') as file:
        file.write('INITIALISE\n\n')

        json.dump(report['initialisation'], file, indent=4, default=convert)

        file.write('\n\n')

        file.write('NB: RnD in EUR million\n\n')

        for company_type in reg.company_types:
            file.write('*********************************************\n')
            file.write(str(company_type.upper()) + '\n')
            file.write('*********************************************\n\n')

            file.write('SELECT PARENT COMPANIES\n\n')

            df = pd.DataFrame.from_dict(
                report['select_parents'], orient='index'
            ).append(
                pd.DataFrame.from_dict(
                    report['load_parent_financials'], orient='index'
                )
            )

            file.write(tabulate(df, tablefmt='simple', headers=df.columns, floatfmt='10,.0f'))
            file.write('\n\n')

            file.write('LOAD SUBSIDIARIES FROM SELECTED PARENT COMPANIES\n\n')

            df = pd.DataFrame.from_dict(
                report['load_subsidiary_identification'], orient='index'
            ).append(
                pd.merge(
                    pd.DataFrame.from_dict(report['select_parents_and_subsidiaries'], orient='index'),
                    pd.DataFrame.from_dict(report['keyword_screen_by_method'], orient='index'),
                    left_index=True, right_index=True
                )
            )

            # .append(
            #     pd.merge(
            #         pd.DataFrame.from_dict(report['load_subsidiary_financials'], orient='index'),
            #         pd.DataFrame.from_dict(report['screen_subsidiary_activities'], orient='index'),
            #         left_index=True, right_index=True
            #         )
            #     )

            file.write(tabulate(df, tablefmt='simple', headers=df.columns, floatfmt='10,.0f'))
            file.write('\n\n')

            file.write('COMPUTE EXPOSURE\n\n')

            file.write('at_parent_level\n\n')

            df = pd.DataFrame.from_dict(report['compute_exposure']['at_parent_level'], orient='index')
            file.write(
                tabulate(df, tablefmt='simple', headers=df.columns, floatfmt=('0.0f', '5.5f', '10,.0f', '10,.0f')))
            file.write('\n\n')

            file.write('at_subsidiary_level\n\n')

            df = pd.DataFrame.from_dict(report['compute_exposure']['at_subsidiary_level'], orient='index')
            file.write(
                tabulate(df, tablefmt='simple', headers=df.columns, floatfmt=('0.0f', '5.5f', '10,.0f', '10,.0f')))
            file.write('\n\n')

            file.write('COMPUTE RND\n\n')

            file.write('at_parent_level\n\n')

            df = pd.DataFrame.from_dict(report['compute_rnd']['at_parent_level'])
            file.write(tabulate(df, tablefmt='simple', headers=df.columns, floatfmt='10,.0f'))
            file.write('\n\n')

            file.write('at_subsidiary_level\n\n')

            df = pd.DataFrame.from_dict(report['compute_rnd']['at_subsidiary_level'])
            file.write(tabulate(df, tablefmt='simple', headers=df.columns, floatfmt='10,.0f'))


def group_soeur_rnd_for_bench(ref_soeur_path):
    print('... load benchmark table')

    soeur_rnd = pd.read_csv(ref_soeur_path, na_values='#N/A')

    print('... and group')

    soeur_rnd_grouped = soeur_rnd.groupby(['year', 'sub_country_2DID_iso', 'sub_world_player']).sum()

    soeur_rnd_grouped.reset_index(inplace=True)

    soeur_rnd_grouped['approach'] = 'SOEUR_rnd_2019b_20200309'

    soeur_rnd_grouped['method'] = 'keep_all'

    soeur_rnd_grouped['vintage'] = soeur_rnd_grouped['approach'] + ' - ' + soeur_rnd_grouped['method']

    soeur_rnd_grouped['type'] = soeur_rnd_grouped['cluster'] = soeur_rnd_grouped['guo_type'] = '#N/A'

    soeur_rnd_grouped.rename(columns={
        'sub_country_3DID_iso': 'country_3DID_iso',
        'sub_world_player': 'world_player',
        'sub_rnd_clean': 'rnd_clean'
    }, inplace=True)

    return soeur_rnd_grouped


def group_soeur_rnd_for_bench(ref_soeur_path):
    print('... load benchmark table')

    soeur_rnd = pd.read_csv(ref_soeur_path, na_values='#N/A')

    print('... and group')

    soeur_rnd_grouped = soeur_rnd.groupby(['year', 'sub_country_2DID_iso', 'sub_world_player']).sum()

    soeur_rnd_grouped.reset_index(inplace=True)

    soeur_rnd_grouped['approach'] = 'SOEUR_rnd_2019b_20200309'

    soeur_rnd_grouped['method'] = 'keep_all'

    soeur_rnd_grouped['vintage'] = soeur_rnd_grouped['approach'] + ' - ' + soeur_rnd_grouped['method']

    soeur_rnd_grouped['type'] = soeur_rnd_grouped['cluster'] = soeur_rnd_grouped['guo_type'] = '#N/A'

    soeur_rnd_grouped.rename(columns={
        'sub_country_3DID_iso': 'country_3DID_iso',
        'sub_world_player': 'world_player',
        'sub_rnd_clean': 'rnd_clean'
    }, inplace=True)

    return soeur_rnd_grouped
